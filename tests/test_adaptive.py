import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
import tempfile
import threading
import time
import unittest
from adaptive_collector import Timeline, Store, deliver

DATA=Path(__file__).resolve().parents[1]/'test_data/test_data_dynamic_timeline.json'
class Adaptive(unittest.TestCase):
    def test_default_eight_machines_from_start(self):
        timeline=Timeline(DATA.parent/'test_data_timeline.json')
        self.assertEqual({r['machine_id'] for r in timeline.read(0)}, {f'machine-{i:02}' for i in range(1,9)})
        self.assertEqual(len(timeline.read(39)),8)
        self.assertEqual(len(timeline.read(40)),8)
    def test_machine_periods_transitions_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.db'; store=Store(path); timeline=Timeline(DATA)
            for i in range(26):
                store.sample_tick('test',timeline,'g','r',1,5,1,1000)
            samples=[__import__('json').loads(r[0]) for r in store.db.execute('SELECT payload FROM outbox')]
            m1=[s['scenario_seconds'] for s in samples if s['machine_id']=='machine-01']
            self.assertEqual(m1,[0,5,10,15,20,25])
            m3=[s for s in samples if s['machine_id']=='machine-03']
            self.assertEqual([s['scenario_seconds'] for s in m3],list(range(10,21))+[25])
            self.assertEqual(m3[10]['send_reason'],'recovered')
            store.db.close();store=Store(path)
            self.assertEqual(store.load('test')['tick'],26)
            first=store.head();store.db.close()
            self.assertEqual(Store(path).head(),first)
    def test_failure_does_not_block_measurements_and_payload_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.db';store=Store(path);timeline=Timeline(DATA)
            store.sample_tick('t',timeline,'g','r',1,5,1,100)
            stop,wake=threading.Event(),threading.Event();attempted=threading.Event();payloads=[]
            def fail(sample):
                payloads.append(sample);attempted.set();raise RuntimeError('offline')
            thread=threading.Thread(target=deliver,args=(path,stop,wake,fail));thread.start()
            try:
                self.assertTrue(attempted.wait(2))
                for i in range(12):store.sample_tick('t',timeline,'g','r',1,5,1,100)
                self.assertEqual(store.load('t')['tick'],13)
                self.assertEqual(store.head()[1]['sample_id'],payloads[0]['sample_id'])
                self.assertIn('delivery_started_at',store.head()[1])
            finally:stop.set();wake.set();thread.join(3)

            sent=[];stop.clear()
            thread=threading.Thread(target=deliver,args=(path,stop,wake,lambda s:sent.append(s)));thread.start()
            deadline=time.monotonic()+3
            while store.head() and time.monotonic()<deadline:time.sleep(.02)
            stop.set();wake.set();thread.join(3)
            self.assertIsNone(store.head())
            self.assertEqual(sent[0],payloads[0])
            store.db.close()
    def test_queue_bound_and_rejected_events_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'s.db');timeline=Timeline(DATA)
            for i in range(12):store.sample_tick('t',timeline,'g','r',1,5,1,2)
            self.assertEqual(store.db.execute('SELECT count(*) FROM outbox').fetchone()[0],2)
            self.assertGreater(store.load('t')['dropped'],0)
            store.db.close()
if __name__=='__main__':unittest.main()

