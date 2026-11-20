
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'apps'))
import config as c
import access_control as ac
from resource_registry import ensure_ae, ensure_cnt
from group_queries import sync_group
from onem2m_client import Client

class AccessControlTests(unittest.TestCase):
    def setUp(self):
        self.mode = patch.object(c,'ACP_ENABLED',True); self.mode.start()
        self.env = patch.dict('os.environ',{},clear=True); self.env.start()
    def tearDown(self):
        self.env.stop(); self.mode.stop()
    def test_roles_distinct_and_not_admin(self):
        origins = [c.role_origin(r) for r in ('collector','analyzer','forwarder','dashboard')]
        self.assertEqual(len(set(origins)),4)
        self.assertNotIn(c.ADMIN_ORIGIN, origins)
    def test_runtime_cannot_use_admin(self):
        with patch.dict('os.environ',{'QF_DASHBOARD_ORIGIN':c.ADMIN_ORIGIN}):
            with self.assertRaises(ValueError): c.role_origin('dashboard')
    def test_dashboard_read_only_in_both_central_policies(self):
        for name in ('archive','group'):
            rules = [r for r in ac.policies()[name] if c.role_origin('dashboard') in r['acor']]
            self.assertTrue(rules)
            self.assertTrue(all(r['acop']==ac.READ for r in rules))
    def test_analyzer_and_forwarder_cannot_create_sensor_values(self):
        for role in ('analyzer','forwarder'):
            rules=[r for r in ac.policies()['sensors'] if c.role_origin(role) in r['acor'] and r['acop'] & 1]
            self.assertEqual([r['acod'] for r in rules], [[{'chty':[23]}]])
    def test_secure_runtime_never_registers_ae(self):
        client=Mock()
        self.assertEqual(ensure_ae(client,'mn','analyzer'),'mn/analyzer')
        client.call.assert_called_once_with('GET','mn/analyzer')
        client.ensure.assert_not_called()
    def test_new_machine_gets_explicit_policy(self):
        client=Mock()
        with patch.object(c,'MN_BASE','mn'):
            ensure_cnt(client,'mn/collector-01','machine-new')
        self.assertEqual(client.ensure.call_args.args[2]['acpi'], [ac.policy_ref('mn','sensors')])
    def test_policy_changes_existing_rules_and_protects_itself(self):
        client=Mock()
        ac.provision_policy(client,'mn','sensors',ac.policies()['sensors'])
        attrs=client.call.call_args.args[2]['m2m:acp']
        self.assertEqual([r for r in attrs['pvs']['acr'] if r['acop'] & 4], [ac.rule(c.ADMIN_ORIGIN,63)])
        self.assertFalse(any('*' in r['acor'] for r in attrs['pv']['acr']))
    def test_group_fanout_has_member_access_policy(self):
        client=Mock();client.ensure.return_value={'m2m:grp':{'mid':['mn/m/telemetry']}}
        with patch('group_queries.discover_machines',return_value=[{'path':'mn/m'}]):
            sync_group(client)
        attrs=client.ensure.call_args.args[2]
        self.assertEqual(attrs['macp'],[ac.policy_ref(c.IN_BASE,'group')])
    def test_legacy_mode_uses_existing_origin(self):
        with patch.object(c,'ACP_ENABLED',False):
            self.assertEqual(c.role_origin('dashboard'),c.ORIGIN)
    def test_runtime_http_origin(self):
        response=Mock(ok=True, headers={},content=b'{}'); response.json.return_value={}
        with patch('onem2m_client.requests.request',return_value=response) as request:
            Client('http://example.invalid',c.role_origin('dashboard')).call('GET','archive')
        self.assertEqual(request.call_args.kwargs['headers']['X-M2M-Origin'],c.role_origin('dashboard'))

if __name__=='__main__':unittest.main()

