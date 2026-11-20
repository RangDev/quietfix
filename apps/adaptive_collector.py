
import hashlib
import json
import logging
import math
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import config as c
from device_model import normalize, machine_status
from onem2m_client import collector_client
from resource_registry import publish

class Timeline:
    def __init__(self, path):
        raw=Path(path).read_bytes()
        value=json.loads(raw)
        self.duration=value['duration_seconds']
        if isinstance(self.duration,bool) or not isinstance(self.duration,(int,float)) or not math.isfinite(self.duration) or self.duration<=0:
            raise ValueError('duration_seconds must be positive and finite')
        self.frames=[]
        seen=set()
        for frame in value['frames']:
            at=frame['at_seconds']
            if isinstance(at,bool) or not isinstance(at,(int,float)) or not math.isfinite(at) or not 0<=at<self.duration:
                raise ValueError('Invalid at_seconds')
            sample=normalize(frame)
            key=(at,sample['machine_id'])
            if key in seen: raise ValueError('Duplicate machine/time frame')
            seen.add(key)
            self.frames.append((at,sample))
        if not self.frames: raise ValueError('Empty timeline')
        self.frames.sort(key=lambda item:item[0])
        self.fingerprint=hashlib.sha256(raw).hexdigest()
    def read(self, elapsed):
        phase=elapsed%self.duration
        current={}
        for at,row in self.frames:
            if at<=phase: current[row['machine_id']]=row
        return list(current.values())

def status_of(sample):
    return machine_status(sample['sensors'])

def reason_for(previous, status, elapsed, normal_period, abnormal_period):
    if previous is None: return 'initial'
    if status=='abnormal' and previous['status']!='abnormal': return 'abnormal_enter'
    if previous['status']=='abnormal' and status=='normal': return 'recovered'
    if status!=previous['status']: return 'status_changed'
    if elapsed-previous['queued_at']+1e-9 >= (abnormal_period if status=='abnormal' else normal_period):
        return 'abnormal_repeat' if status=='abnormal' else 'periodic'
    return None

class Store:
    def __init__(self, path):
        self.db=sqlite3.connect(path, timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS schedule (key TEXT PRIMARY KEY, payload TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT)')
    def load(self,key):
        row=self.db.execute('SELECT payload FROM schedule WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else {'tick':0,'machines':{},'dropped':0}
    def sample_tick(self,key,timeline,collector,replay,measure,normal,abnormal,capacity):
        with self.db:
            state=self.load(key)
            elapsed=state['tick']*measure
            for row in timeline.read(elapsed):
                mid=row['machine_id']; status=status_of(row)
                previous=state['machines'].get(mid)
                reason=reason_for(previous,status,elapsed,normal,abnormal)
                if reason is None: continue
                if self.db.execute('SELECT count(*) FROM outbox').fetchone()[0]>=capacity:
                    state['dropped']+=1
                    logging.error('Outbox full: rejected sample machine=%s dropped=%s',mid,state['dropped'])
                    continue
                stamp=datetime.now(timezone.utc).isoformat()
                sample={**row,'collector_id':collector,'timestamp':stamp,'simulated':True,
                        'sample_id':hashlib.sha256(f'{key}:{mid}:{state["tick"]}'.encode()).hexdigest(),
                        'sequence':state['tick'],'scenario_seconds':elapsed,'replay_id':replay,
                        'local_status':status,'send_reason':reason,'measure_period_seconds':measure,
                        'normal_period_seconds':normal}
                self.db.execute('INSERT INTO outbox(payload) VALUES (?)',(json.dumps(sample),))
                state['machines'][mid]={'status':status,'queued_at':elapsed}
            state['tick']+=1
            self.db.execute('INSERT OR REPLACE INTO schedule VALUES (?,?)',(key,json.dumps(state)))
        return state
    def head(self):
        row=self.db.execute('SELECT id,payload FROM outbox ORDER BY id LIMIT 1').fetchone()
        return (row[0],json.loads(row[1])) if row else None
    def ack(self,ident):
        with self.db:self.db.execute('DELETE FROM outbox WHERE id=?',(ident,))

def deliver(path,stop,notify,send=None):
    store=Store(path)
    send=send or (lambda sample:publish(collector_client(),sample))
    try:
        while not stop.is_set():
            row=store.head()
            if row is None:
                notify.wait(.2);notify.clear();continue
            ident,sample=row
            try:

                if 'delivery_started_at' not in sample:
                    sample['delivery_started_at']=datetime.now(timezone.utc).isoformat()
                    with store.db: store.db.execute('UPDATE outbox SET payload=? WHERE id=?',(json.dumps(sample),ident))
                send(sample)
                store.ack(ident)
                print('SENT',sample['machine_id'],sample['send_reason'],sample['sample_id'],flush=True)
            except Exception:
                logging.exception('Delivery failed; measurement continues')
                stop.wait(max(c.POLL_SECONDS,.1))
    finally:store.db.close()

def run(args):
    values=[args.measure_period,args.normal_period,args.abnormal_period]
    if any(not math.isfinite(v) or v<=0 for v in values) or args.outbox_limit<=0:
        raise ValueError('Periods and outbox limit must be positive and finite')
    timeline=Timeline(args.dataset)
    c.STATE.mkdir(parents=True,exist_ok=True)
    path=c.STATE/('adaptive-'+c.COLLECTOR_ID+'.sqlite3')
    store=Store(path)

    key=f'v4:{c.COLLECTOR_ID}:{timeline.fingerprint}:{args.replay_id}:{values}'
    stop,notify=threading.Event(),threading.Event()
    worker=threading.Thread(target=deliver,args=(path,stop,notify),daemon=True)
    worker.start()
    deadline=time.monotonic()
    try:
        while args.cycles==0 or store.load(key)['tick']*args.measure_period<timeline.duration*args.cycles:
            if not worker.is_alive(): raise RuntimeError('Delivery thread stopped')
            state=store.sample_tick(key,timeline,c.COLLECTOR_ID,args.replay_id,*values,args.outbox_limit)
            notify.set()
            deadline+=args.measure_period

            if deadline<time.monotonic():deadline=time.monotonic()+args.measure_period
            stop.wait(max(0,deadline-time.monotonic()))
        while store.head() is not None:
            if not worker.is_alive(): raise RuntimeError('Delivery thread stopped')
            notify.set();stop.wait(.1)
    finally:
        stop.set();notify.set();worker.join(c.TIMEOUT+1);store.db.close()

