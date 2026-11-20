import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
import tempfile
import unittest
from unittest.mock import patch
from ml_anomaly import Models, train, vector
from ml_manage import generate, evaluate
from analyzer_ae import analyze
import config as c

class MachineLearning(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        train(generate(42,500,'collector-01'),self.tmp.name)
        self.models=Models(self.tmp.name)
        self.sample={**generate(123,1,'collector-01')[0], 'sample_id':'test',
                     'timestamp':'2026-11-20T00:00:00Z'}
    def tearDown(self): self.tmp.cleanup()
    def test_identity_reload_and_missing_model(self):
        first=self.models.predict(self.sample)
        self.assertEqual(first['model_state'],'ready')
        self.assertEqual(first,Models(self.tmp.name).predict(self.sample))
        for field in ['machine_id','collector_id']:
            self.assertEqual(self.models.predict({**self.sample,field:'unknown'})['model_state'],'collecting_baseline')
    def test_ml_below_rule_and_consecutive_reset(self):
        sample={**self.sample,'current_a':6,'temperature_c':65,'vibration_rms_mm_s':5}
        with patch.object(c,'ML_CONSECUTIVE',3):
            result=analyze(sample,self.models)
            self.assertEqual(result['rule_status'],'normal')
            self.assertTrue(result['ml']['is_outlier'])
            self.assertEqual(result['status'],'normal')
            self.assertEqual(analyze(sample,self.models,2)['status'],'abnormal')
        normal={**sample,'temperature_c':46,'vibration_rms_mm_s':2,'current_a':3}
        self.assertEqual(analyze(normal,self.models,2)['ml']['consecutive'],0)
        self.assertEqual(analyze({**sample,'temperature_c':80},self.models)['status'],'abnormal')
    def test_incomplete_and_invalid_training(self):
        sample=dict(self.sample);del sample['current_a']
        self.assertEqual(self.models.predict(sample)['model_state'],'invalid_input')
        with self.assertRaises(ValueError):vector({**self.sample,'current_a':float('nan')})
        with self.assertRaises(ValueError):train([{**self.sample,'label':'abnormal'}],self.tmp.name)
    def test_retry_and_restart_do_not_increment_twice(self):
        from unittest.mock import Mock
        from worker_state import State
        from analyzer_ae import step
        sample={**self.sample,'current_a':6,'temperature_c':65,'vibration_rms_mm_s':5}
        machine=dict(path='mn/m',collector_id='collector-01',machine_id='machine-01')
        client=Mock()
        client.records.return_value=[sample]
        client.put.side_effect=[RuntimeError('lost response'),None,None]
        with patch.object(c,'STATE',Path(self.tmp.name)), patch('analyzer_ae.ensure_analyzer',return_value='results'), patch('analyzer_ae.discover_machines',return_value=[machine]):
            state=State('retry')
            with self.assertRaises(RuntimeError):step(client,state,self.models)
            state.db.close()
            state=State('retry')
            step(client,state,self.models)
            step(client,state,self.models)
            self.assertEqual(client.put.call_count,2)
            self.assertEqual(client.put.call_args_list[0],client.put.call_args_list[1])
            self.assertEqual(state.position('ml-streak:collector-01:machine-01'),1)
            state.db.close()

    def test_heldout_comparison(self):
        rows=generate(987,100,'collector-01')
        rows += [{**r,'current_a':6,'temperature_c':65,'vibration_rms_mm_s':5,'label':'abnormal'} for r in generate(456,100,'collector-01')]
        result=evaluate(rows,self.models)
        self.assertGreater(result['ml']['detection_rate'],.9)
        self.assertLess(result['ml']['false_positive_rate'],.1)
        self.assertEqual(result['rule']['detection_rate'],0)
if __name__=='__main__':unittest.main()

