import base64,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
import config as c
from semantics import canonical,descriptor,discover_paths
from device_model import normalize
from analyzer_ae import analyze
class SemanticsTests(unittest.TestCase):
    def test_vendor_aliases_and_units(self):
        sensors=[{'sensor_id':'t','type':'temp','unit':'Fahrenheit','value':167}, {'sensor_id':'i','type':'ampere','unit':'mA','value':4000}]
        with patch.object(c,'SEMANTIC_ENABLED',True):row=normalize({'machine_id':'m','sensors':sensors})
        self.assertEqual(row['sensors'][0]['value'],75)
        self.assertEqual(row['sensors'][1]['value'],4)
        with patch.object(c,'SEMANTIC_ENABLED',True):self.assertEqual(analyze({**row,'sample_id':'s','collector_id':'c','timestamp':'2026-11-18T00:00:00Z','simulated':True})['status'],'abnormal')
    def test_actual_rdf_query_finds_temperature_by_meaning(self):
        attrs={'collectorId':'c','machineId':'m','sensorId':'vendor-t','sensorType':'temperature','unit':'°C','value':75,'timestamp':'2026-11-18T00:00:00Z'}
        dsp=descriptor('mn/c/m/sensor-t',attrs)
        client=Mock();client.call.side_effect=[{'m2m:uril':['mn/c/m/sensor-t/meaning']},{'m2m:smd':{'dcrp':4,'dsp':dsp}}]
        self.assertEqual(discover_paths(client,'mn','temperature'),['mn/c/m/sensor-t'])
        self.assertIn(b'https://saref.etsi.org/core/',base64.b64decode(dsp))
    def test_unknown_unit_not_guessed(self):
        self.assertEqual(canonical({'type':'temp','unit':'unknown','value':123})['unit'],'unknown')
    def test_descriptor_cannot_redirect_discovery(self):
        attrs={'collectorId':'c','machineId':'m','sensorId':'t','sensorType':'temperature','unit':'°C','value':1,'timestamp':'2026-11-18T00:00:00Z'}
        client=Mock();client.call.side_effect=[{'m2m:uril':['mn/c/t/meaning']},{'m2m:smd':{'dcrp':4,'dsp':descriptor('outside/admin',attrs)}}]
        self.assertEqual(discover_paths(client,'mn'),[])

