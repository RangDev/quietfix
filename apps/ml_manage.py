"""Generate synthetic normal baselines, explicitly train, or evaluate held-out rows."""
import argparse
import json
from pathlib import Path
import random
import config as c
from ml_anomaly import Models, train
from device_model import normalize, machine_status

def generate(seed, count, collector):
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        for mid, base in [('machine-01', 46), ('machine-02', 47)]:
            load = rng.uniform(-1, 1)
            rows.append(dict(collector_id=collector, machine_id=mid, sequence=i,
                temperature_c=base+load*2+rng.gauss(0,.5),
                vibration_rms_mm_s=2+load*.2+rng.gauss(0,.08),
                current_a=3+load*.3+rng.gauss(0,.1), label='normal', simulated=True))
    return rows

def evaluate(rows, models):
    counts = {name: dict(tp=0, fp=0, tn=0, fn=0) for name in ('ml', 'rule')}
    for row in rows:
        if row.get('label') not in ('normal','abnormal'):
            raise ValueError('Test rows require normal/abnormal labels')
        ml = models.predict(row)
        if ml['model_state'] != 'ready':
            raise ValueError('All evaluation rows require a ready model and valid sensors')
        actual = row['label'] == 'abnormal'
        for method, predicted in [('ml',ml['is_outlier']),
                ('rule',machine_status(normalize(row)['sensors'])=='abnormal')]:
            counts[method]['tp' if actual and predicted else 'fn' if actual else 'fp' if predicted else 'tn'] += 1
    for metrics in counts.values():
        metrics['detection_rate'] = metrics['tp']/(metrics['tp']+metrics['fn']) if metrics['tp']+metrics['fn'] else None
        metrics['false_positive_rate'] = metrics['fp']/(metrics['fp']+metrics['tn']) if metrics['fp']+metrics['tn'] else None
    return counts

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['generate','generate-test','train','evaluate'])
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--model-dir',type=Path,default=c.ML_MODEL_DIR)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--count',type=int,default=1000)
    p.add_argument('--collector-id',default=c.COLLECTOR_ID)
    a=p.parse_args()
    if a.command in ('generate','generate-test'):
        a.dataset.parent.mkdir(parents=True,exist_ok=True)
        rows=generate(a.seed,a.count,a.collector_id)
        if a.command=='generate-test':
            for row in rows:
                phase=row['sequence']/a.count
                if .4 <= phase < .7:
                    row.update(temperature_c=65, vibration_rms_mm_s=5, current_a=6, label='abnormal')
                elif .7 <= phase < .9:
                    delta=(phase-.7)/.2
                    row['temperature_c']+=20*delta
                    row['vibration_rms_mm_s']+=3*delta
                    row['current_a']+=3*delta
                    row['label']='abnormal'
        a.dataset.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        rows=json.loads(a.dataset.read_text(encoding='utf-8'))
        if a.command=='train': print('Trained models:',train(rows,a.model_dir))
        else:
            from ml_anomaly import identity
            groups={}
            for row in rows: groups.setdefault('/'.join(identity(row)),[]).append(row)
            print(json.dumps({key:evaluate(group,Models(a.model_dir)) for key,group in groups.items()},indent=2))
if __name__=='__main__':main()
