
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
import config as c
from device_model import normalize
from flex_model import KIND,CND,LABEL,publish_readings,discover,with_typed_readings

class FlexModelTests(unittest.TestCase):
    def setUp(self):
        self.sample=normalize({'collector_id':'collector-01','machine_id':'m1','sample_id':'s1',
            'timestamp':'2026-11-18T00:00:00+00:00','temperature_c':76,'vibration_rms_mm_s':2,'current_a':3})
        self.sample['simulated']=True
    def test_model_file_defines_numeric_value_and_unit(self):
        model=json.loads((Path(__file__).resolve().parents[1]/'models'/'quietfix.fcp').read_text())[0]
        self.assertEqual(model['cnd'],CND)
        attrs={x['sname']:x for x in model['attributes']}
        self.assertEqual(attrs['value']['type'],'float')
        self.assertEqual(attrs['unit']['type'],'string')
    def test_projection_has_explicit_policy_and_typed_fields(self):
        client=Mock();client.ensure.side_effect=lambda parent,kind,attrs,ty:{kind:copy.deepcopy(attrs)}
        with patch.object(c,'ACP_ENABLED',True):publish_readings(client,'mn/collector-01/machine-m1',self.sample)
        self.assertEqual(client.ensure.call_count,3)
        attrs=client.ensure.call_args_list[0].args[2]
        self.assertEqual(attrs['unit'],'°C');self.assertEqual(attrs['value'],76)
        self.assertIn('sensors-fcnt',attrs['acpi'][0]);client.call.assert_not_called()
    def test_older_sample_does_not_regress_projection(self):
        client=Mock()
        client.ensure.side_effect=lambda parent,kind,attrs,ty:{kind:{**attrs,'timestamp':'2026-11-19T00:00:00+00:00'}}
        publish_readings(client,'mn/m',self.sample);client.call.assert_not_called()
    def test_matching_snapshot_used_and_order_preserved(self):
        attrs={'sampleId':'s1','timestamp':self.sample['timestamp'],'collectorId':'collector-01','machineId':'m1'}
        machine={'_typed':[(attrs,s) for s in reversed(self.sample['sensors'])]}
        result=with_typed_readings(self.sample,machine)
        self.assertEqual(result['sensors'],self.sample['sensors']);self.assertEqual(result['data_model'],CND)
    def test_partial_or_different_snapshot_cannot_mix_values(self):
        attrs={'sampleId':'old','timestamp':self.sample['timestamp'],'collectorId':'collector-01','machineId':'m1'}
        self.assertIs(with_typed_readings(self.sample,{'_typed':[(attrs,self.sample['sensors'][0])]}),self.sample)
        attrs['sampleId']='s1'
        self.assertIs(with_typed_readings(self.sample,{'_typed':[(attrs,self.sample['sensors'][0])]}),self.sample)
    def test_discovery_uses_resource_type_and_specialization(self):
        client=Mock();client.call.return_value={'m2m:uril':[]}
        self.assertEqual(list(discover(client,'mn')),[])
        query=client.call.call_args.args[1]
        self.assertIn('ty=28',query);self.assertIn('cnd='+CND,query);self.assertIn('lbl='+LABEL,query)
    def test_incorrect_unit_keeps_existing_unassessed_rule(self):
        from analyzer_ae import analyze
        row=copy.deepcopy(self.sample);row['sensors'][0]['unit']='F'
        self.assertEqual(analyze(row)['sensors'][0]['status'],'unassessed')

