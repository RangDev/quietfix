"""HTTP contract tests with a local oneM2M test double, not a live ACME server."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

APPS = Path(__file__).resolve().parents[1] / 'apps'
sys.path.insert(0, str(APPS))
import config as c
from device_model import normalize
from sensor_simulator import SensorSimulator
from onem2m_client import Client
from resource_registry import publish, discover_machines
from analyzer_ae import analyze
import dashboard
from event_worker import Notifications, subscribe
from group_queries import sync_group, latest_group
import requests

class CSEHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path.strip('/')
        resources = self.server.resources
        if parsed.query:
            if path not in resources:
                return self.reply(404, {})
            query = parse_qs(parsed.query)
            ty = int(query['ty'][0])
            lbl = query.get('lbl', [None])[0]
            uris = [key for key, value in resources.items() if key.startswith(path+'/')
                    and value['ty'] == ty and (lbl is None or lbl in value.get('lbl', []))]
            return self.reply(200, {'m2m:uril': uris})
        if path.endswith('/fopt/la'):
            group=resources.get(path[:-8])
            if group is None:
                return self.reply(404,{})
            responses=[]
            for member in group['mid']:
                children=[v for k,v in resources.items() if k.rsplit('/',1)[0]==member.strip('/') and v['ty']==4]
                responses.append({'rsc':2000,'pc':{'m2m:cin':children[-1]}} if children else {'rsc':4004})
            return self.reply(200,{'m2m:agr':{'m2m:rsp':responses}})
        if path.endswith('/la'):

            parent = path[:-3]
            uris = [key for key, value in resources.items() if key.rsplit('/', 1)[0] == parent and value['ty'] == 4]
            if not uris:
                return self.reply(404, {})
            path = uris[-1]
        if path not in resources:
            return self.reply(404, {})
        resource = resources[path]
        kind = {2: 'm2m:ae', 3: 'm2m:cnt', 4: 'm2m:cin', 5: 'm2m:cb', 9: 'm2m:grp', 23: 'm2m:sub'}[resource['ty']]
        self.reply(200, {kind: resource})

    def do_POST(self):
        parent = self.path.strip('/')
        resources = self.server.resources
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        kind, attrs = next(iter(payload.items()))
        ty = { 'm2m:ae': 2, 'm2m:cnt': 3, 'm2m:cin': 4, 'm2m:grp':9, 'm2m:sub':23 }[kind]
        if parent not in resources:
            return self.reply(404, {})
        target = parent+'/'+attrs['rn']
        if target in resources:
            return self.reply(409, {})
        if ty == 23:
            for url in attrs['nu']:
                requests.post(url,json={'m2m:sgn':{'vrq':True}},timeout=2).raise_for_status()
        resources[target] = {**attrs, 'ty': ty}
        if ty == 4:
            children = [key for key, value in resources.items() if key.rsplit('/',1)[0] == parent and value['ty'] == 4]
            for key in children[:-resources[parent].get('mni',1000)]:
                del resources[key]
        self.reply(201, {kind: resources[target]})
        if ty == 4:
            for key,value in list(resources.items()):
                if key.rsplit('/',1)[0]==parent and value['ty']==23:
                    for url in value['nu']:
                        requests.post(url,json={'m2m:sgn':{'sur':key,'nev':{'net':3,'rep':{'m2m:cin':resources.get(target,attrs)}}}},timeout=2)

    def do_PUT(self):
        path=self.path.strip('/')
        if path not in self.server.resources:
            return self.reply(404,{})
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        kind,attrs=next(iter(payload.items()))
        self.server.resources[path].update(attrs)
        self.reply(200,{kind:self.server.resources[path]})

class DynamicFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(('127.0.0.1',0), CSEHandler)
        self.server.resources = {'mn': {'ty':5}, 'in': {'ty':5}}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.settings = patch.multiple(c, MN_BASE='mn', IN_BASE='in', MN_URL=self.url, IN_URL=self.url)
        self.settings.start()
        self.env = {**os.environ, 'QF_MN_BASE':'mn', 'QF_IN_BASE':'in',
                    'QF_MN_URL':self.url, 'QF_IN_URL':self.url,
                    'QF_STATE_DIR':self.tmp.name, 'QF_COLLECTOR_ID':'collector-01'}

    def tearDown(self):
        self.settings.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def run_app(self, name, *args, **env):
        return subprocess.run([sys.executable, str(APPS/name), *args], env={**self.env, **env},
                              capture_output=True, text=True, check=True, timeout=20)

    def pipeline(self):
        self.run_app('analyzer_ae.py','--once')
        self.run_app('forwarder_ae.py','--once')

    def test_dynamic_registration_restart_extension_and_gateway_namespace(self):
        # No setup script or predefined machine list.
        args = ('--dataset',str(APPS.parent/'test_data/test_data_expanded.json'),'--interval','0','--cycles','1')
        self.run_app('collector_ae.py', *args)
        self.pipeline()
        snap = dashboard.snapshot()
        self.assertEqual(len(snap['machines']),4)
        machine = next(m for m in snap['machines'] if m['machine_id']=='machine-03')
        self.assertEqual(len(machine['sensors']),5)
        self.assertEqual(machine['analysis']['status'],'normal')
        pressure = next(s for s in machine['analysis']['sensors'] if s['sensor_id']=='pressure')
        self.assertEqual(pressure['status'],'unassessed')
        self.assertEqual(machine['analysis']['coverage'],'partial')
        unknown = next(m for m in snap['machines'] if m['machine_id']=='machine-04')
        self.assertEqual(unknown['analysis']['status'],'unassessed')
        self.assertIn('mn/collector-01/machine-machine-03/telemetry', self.server.resources)
        self.assertNotIn('mn/collector-02',self.server.resources)
        # Re-running all processes with the same checkpoint adds no samples/results.
        before = copy.deepcopy(self.server.resources)
        self.run_app('collector_ae.py', *args)
        self.pipeline()
        self.assertEqual(before,self.server.resources)
        # A second collector may reuse machine IDs without mixing data or alerts.
        self.run_app('collector_ae.py', *args, QF_COLLECTOR_ID='gateway-west')
        self.pipeline()
        snap = dashboard.snapshot()
        self.assertEqual(len(snap['machines']),8)
        for m in snap['machines']:
            self.assertEqual(m['collector_id'],m['analysis']['collector_id'])
            self.assertEqual(m['telemetry']['sample_id'],m['analysis']['sample_id'])
        cache = dashboard.DashboardCache()
        cache.refresh()
        self.assertEqual(len(cache.read()[1]['alerts']),2)
        cache.refresh()
        self.assertEqual(len(cache.read()[1]['alerts']),2)

    def test_later_machine_and_sensor_appear_without_worker_reconfiguration(self):
        client = Client(self.url)
        def sample(mid, sid, sensors):
            return {**normalize({'machine_id':mid,'sensors':sensors}), 'collector_id':'gateway',
                    'sample_id':sid,'timestamp':'2026-11-17T10:00:00Z','simulated':True}
        temp = {'sensor_id':'temp','type':'temperature','unit':'°C','value':75}
        publish(client,sample('machine-01','first',[temp]))
        self.pipeline()
        self.assertEqual(len(dashboard.snapshot()['machines']),1)
        pressure = {'sensor_id':'pressure','type':'pressure','unit':'bar','value':2}
        publish(client,sample('machine-01','second',[temp,pressure]))
        publish(client,sample('machine-99','third',[temp]))
        self.pipeline()
        snap=dashboard.snapshot()
        self.assertEqual(len(snap['machines']),2)
        m=next(m for m in snap['machines'] if m['machine_id']=='machine-01')
        self.assertEqual(len(m['sensors']),2)
        self.assertEqual(m['analysis']['status'],'abnormal')
        # A registered sensor omitted from a later complete snapshot is not given an old value.
        publish(client,sample('machine-01','fourth',[temp]))
        self.pipeline()
        m=next(m for m in dashboard.snapshot()['machines'] if m['machine_id']=='machine-01')
        self.assertEqual(len(m['sensors']),2)
        self.assertEqual(len(m['telemetry']['sensors']),1)
        # Lost POST response retry is idempotent at the CIN level.
        publish(client,sample('machine-01','fourth',[temp]))
        self.assertEqual(len(list(client.records('mn/gateway/machine-machine-01/telemetry'))),3)
        # Metadata remains one CIN with a union of all registered sensor descriptors.
        self.assertEqual(len(list(client.records('mn/gateway/machine-machine-01/metadata'))),1)

    def test_running_workers_discover_new_devices_without_restart(self):
        workers = [subprocess.Popen([sys.executable,str(APPS/name)], env={**self.env,'QF_POLL_SECONDS':'0.05'},
                                   stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
                   for name in ('analyzer_ae.py','forwarder_ae.py')]
        def wait_for(predicate):
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                if predicate(dashboard.snapshot()):
                    return
                time.sleep(0.05)
            self.fail('Live polling workers did not reflect new devices')
        def reading(mid,sid,sensors):
            return {**normalize({'machine_id':mid,'sensors':sensors}), 'collector_id':'live-gateway',
                    'sample_id':sid,'timestamp':'2026-11-17T10:00:00Z','simulated':True}
        try:
            temp={'sensor_id':'temp','type':'temperature','unit':'°C','value':76}
            client=Client(self.url)
            publish(client,reading('m1','s1',[temp]))
            wait_for(lambda v:len(v['machines'])==1 and v['machines'][0].get('analysis') is not None)
            pressure={'sensor_id':'pressure','type':'pressure','unit':'bar','value':2}
            publish(client,reading('m1','s2',[temp,pressure]))
            publish(client,reading('m2','s3',[pressure]))
            wait_for(lambda v:len(v['machines'])==2 and
                     all(m.get('analysis') is not None for m in v['machines']) and
                     any(len(m['sensors'])==2 and m['telemetry']['sample_id']=='s2' for m in v['machines']))
            self.assertTrue(all(worker.poll() is None for worker in workers))
        finally:
            for worker in workers:
                worker.terminate()
                worker.communicate(timeout=5)

    def test_live_notification_wakes_analyzer_before_reconcile_deadline(self):
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        client=Client(self.url)
        sensor=SensorSimulator(APPS.parent/'test_data/test_data_expanded.json')
        first=sensor.read_measurements(0)
        publish(client,first)
        env={**self.env,'QF_ANALYZER_NOTIFY_URL':f'http://127.0.0.1:{port}/notify',
             'QF_ANALYZER_NOTIFY_PORT':str(port),'QF_NOTIFY_HOST':'127.0.0.1','QF_RECONCILE_SECONDS':'30'}
        worker=subprocess.Popen([sys.executable,str(APPS/'analyzer_ae.py')],env=env,
                                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        def wait_until(check):
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                if check(): return
                time.sleep(.02)
            self.fail('Notification processing timed out before 30s fallback')
        def has_result(sid):
            return any(v['ty']==4 and k.startswith('mn/analyzer/results/') and
                       json.loads(v['con'])['sample_id']==sid for k,v in list(self.server.resources.items()))
        try:
            wait_until(lambda:has_result(first['sample_id']))
            second=sensor.read_measurements(5)
            publish(client,second)
            wait_until(lambda:has_result(second['sample_id']))
        finally:
            worker.terminate()
            worker.communicate(timeout=5)

    def test_subscriptions_verification_wakeup_and_dynamic_group(self):
        client=Client(self.url)
        sensor=SensorSimulator(APPS.parent/'test_data/test_data_expanded.json')
        publish(client,sensor.read_measurements(0))
        with Notifications('127.0.0.1',0) as receiver:
            url=f'http://127.0.0.1:{receiver.server.server_port}/notify'
            subscribe(client,'analyzer',url)
            self.assertFalse(receiver.wake.is_set())  # verification is acknowledged, not processed
            publish(client,sensor.read_measurements(1))
            subscribe(client,'analyzer',url)  # newly discovered machine gets a subscription
            publish(client,sensor.read_measurements(6))
            self.assertTrue(receiver.wake.wait(2))
            self.pipeline()
            group=latest_group(client)
            self.assertEqual(len(group),2)
            self.assertEqual(group[('collector-01','machine-02')]['sequence'],6)
            publish(client,sensor.read_measurements(2))
            self.pipeline()
            self.assertEqual(len(latest_group(client)),3)
            # Repeated group reconciliation must update members without duplicates.
            sync_group(client)
            members=self.server.resources['in/archive/telemetryGroup']['mid']
            self.assertEqual(len(members),len(set(members)))
            # Empty member is a per-member error, not a failure of the whole response.
            del self.server.resources[next(k for k,v in self.server.resources.items()
                if k.startswith('in/archive/collector-01/machine-machine-01/telemetry/') and v['ty']==4)]
            self.assertEqual(len(latest_group(client)),2)
            self.assertEqual(len(dashboard.snapshot()['machines']),3)

    def test_adaptive_cli_end_to_end(self):
        data={'duration_seconds':.1,'frames':[
            {'at_seconds':0,'machine_id':'m1','temperature_c':40},
            {'at_seconds':0,'machine_id':'m2','temperature_c':45},
            {'at_seconds':.03,'machine_id':'m1','temperature_c':80},
            {'at_seconds':.06,'machine_id':'m1','temperature_c':40}]}
        dataset=Path(self.tmp.name)/'timeline.json';dataset.write_text(json.dumps(data))
        self.run_app('collector_ae.py','--dataset',str(dataset),'--cycles','1',
                     '--measure-period','.01','--normal-period','.05','--abnormal-period','.01')
        self.pipeline()
        samples=list(Client(self.url).records('mn/collector-01/machine-m1/telemetry'))
        self.assertIn('abnormal_enter',[s['send_reason'] for s in samples])
        self.assertIn('recovered',[s['send_reason'] for s in samples])
        self.assertEqual(len(dashboard.snapshot()['machines']),2)
        before=copy.deepcopy(self.server.resources)
        self.run_app('collector_ae.py','--dataset',str(dataset),'--cycles','1',
                     '--measure-period','.01','--normal-period','.05','--abnormal-period','.01')
        self.assertEqual(before,self.server.resources)

    def test_alert_limit_and_cached_error(self):
        results=[{'collector_id':'g','machine_id':'m','sample_id':str(i),
                  'timestamp':f'{i:03}','status':'abnormal'} for i in range(15)]
        cache=dashboard.DashboardCache()
        with patch.object(dashboard,'snapshot',side_effect=lambda:{'machines':[],'_results':results}):
            cache.refresh();cache.refresh()
        alerts=cache.read()[1]['alerts']
        self.assertEqual([a['sample_id'] for a in alerts],[str(i) for i in range(14,4,-1)])
        with patch.object(dashboard,'snapshot',side_effect=RuntimeError('offline')):
            cache.refresh()
        self.assertEqual(cache.read()[1]['alerts'],alerts)
        self.assertEqual(cache.read()[1]['error'],'offline')

class Schema(unittest.TestCase):
    def test_threshold_boundaries_multiple_sensors_and_unknown_units(self):
        sample={'sample_id':'s','collector_id':'g','machine_id':'m','timestamp':'t','simulated':True,
                'sensors':[{'sensor_id':'t1','type':'temperature','unit':'°C','value':74.99},
                           {'sensor_id':'t2','type':'temperature','unit':'°C','value':75},
                           {'sensor_id':'v','type':'vibration_rms','unit':'mm/s','value':7},
                           {'sensor_id':'f','type':'temperature','unit':'°F','value':80}]}
        result=analyze(sample)
        self.assertEqual(result['status'],'abnormal')
        self.assertEqual([s['status'] for s in result['sensors']],['normal','abnormal','abnormal','unassessed'])

    def test_old_dataset_and_validation(self):
        sensor=SensorSimulator(APPS.parent/'test_data/test_data.json')
        self.assertEqual(len(sensor.read_measurements(0)['sensors']),3)
        bad=[{'machine_id':'../m','temperature_c':1},
             {'machine_id':'m','sensors':[]},
             {'machine_id':'m','sensors':[{'sensor_id':'t','value':True}]},
             {'machine_id':'m','sensors':[{'sensor_id':'t','value':float('nan')}]},
             {'machine_id':'m','sensors':[{'sensor_id':'t','value':1}]*2}]
        for row in bad:
            with self.subTest(row=row),self.assertRaises(ValueError):
                normalize(row)

if __name__=='__main__':
    unittest.main()
