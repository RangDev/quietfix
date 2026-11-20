import json,os,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
import config as c
from routing import atomic_write,read_route,guarded,route_lock
from onem2m_client import Client
class RoutingTests(unittest.TestCase):
    def test_runtime_switch_and_exclusive_barrier(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'QF_ROUTE_FILE':tmp+'/route.json'}),patch.object(c,'MN_URL','http://old'),patch.object(c,'MN_BASE','old'),patch.object(c,'MQTT_CSE_ID',c.MQTT_CSE_ID):
            atomic_write(tmp+'/route.json',{'url':'http://new','base':'new','cse_id':'/id-new'})
            entered=threading.Event()
            @guarded
            def step(client):entered.set();return client.url
            client=Client('http://old')
            with route_lock(exclusive=True):
                thread=threading.Thread(target=lambda:step(client));thread.start()
                self.assertFalse(entered.wait(.1))
            thread.join(2);self.assertTrue(entered.is_set());self.assertEqual(client.url,'http://new')
    def test_invalid_route_rejected(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'QF_ROUTE_FILE':tmp+'/route.json'}):
            atomic_write(tmp+'/route.json',{'url':'file:///bad','base':'x'})
            with self.assertRaises(ValueError):read_route()
    def test_atomic_writer_replaces_complete_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=tmp+'/route.json';atomic_write(path,{'a':1});atomic_write(path,{'b':2})
            self.assertEqual(json.loads(Path(path).read_text()),{'b':2})

