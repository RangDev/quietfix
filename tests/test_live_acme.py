"""Opt-in real ACME integration; creates isolated in-memory CSE processes."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
import config as c
from onem2m_client import Client, OneM2MError
from resource_registry import publish, discover_machines
from analyzer_ae import step as analyze_step
from forwarder_ae import step as forward_step
from flex_model import KIND, CND, with_typed_readings
from worker_state import State
import dashboard

@unittest.skipUnless(os.getenv('QF_RUN_LIVE_ACME')=='1','Set QF_RUN_LIVE_ACME=1 with acmecse installed')
class LiveACME(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import acmecse
        cls.tmp=tempfile.TemporaryDirectory(); cls.procs=[];cls.logs=[]
        cls.patchers=[]
        try:
            for base,attr in [('mn','MN'),('central','IN')]:
                home=Path(cls.tmp.name)/base; (home/'init').mkdir(parents=True)
                (home/'init'/'quietfix.fcp').write_bytes((Path(__file__).resolve().parents[1]/'models'/'quietfix.fcp').read_bytes())
                with socket.socket() as s:
                    s.bind(('127.0.0.1',0));port=s.getsockname()[1]
                url=f'http://127.0.0.1:{port}'
                config=f'''[basic.config]
cseType=IN
cseID=id-{base}
cseName={base}
adminID=CAdmin
cseHost=127.0.0.1
httpPort={port}
networkInterface=127.0.0.1
databaseType=memory
logLevel=error
consoleTheme=dark
consoleType=simple
registrarCseHost=
registrarCseID=
registrarCseName=
registrarCsePort=0
secret=local-integration-only
serviceProviderID=//acme.example.com
[cse]
cseID=/id-{base}
resourceID=id-{base}
resourceName={base}
originator=CAdmin
resourcesPath={Path(acmecse.__file__).parent/'init'}
enableRemoteCSE=false
[http]
port={port}
address={url}
listenIF=127.0.0.1
[database]
type=memory
'''
                (home/'acme.ini').write_text(config)
                log=open(home/'server.log','w+');cls.logs.append(log)
                bootstrap="from acmecse.runtime.Configuration import Configuration; Configuration._print=staticmethod(print); Configuration._error=staticmethod(print); from acmecse.runtime.Logging import Logging; Logging.logErr=classmethod(lambda cls,*a,**k:print(a,k,flush=True)); from acmecse.__main__ import main; main()"
                proc=subprocess.Popen([sys.executable,'-c',bootstrap,'--base-directory',str(home),'--headless',
                    '--no-mqtt','--no-coap','--no-ws','--no-remote-cse','--log-level','debug'],stdout=log,stderr=log)
                cls.procs.append(proc)
                for _ in range(100):
                    try:
                        Client(url).call('GET',base);break
                    except Exception:
                        if proc.poll() is not None:
                            log.seek(0); output=log.read(); Path('/tmp/qf-live-last.log').write_text(output); raise RuntimeError(output)
                        time.sleep(.1)
                else:
                    log.seek(0);raise RuntimeError('ACME startup timeout: '+log.read())
                for name,value in [(attr+'_URL',url),(attr+'_BASE',base)]:
                    pp=patch.object(c,name,value);pp.start();cls.patchers.append(pp)
            for name,value in [('FLEX_ENABLED',True),('ACP_ENABLED',True),('STATE',Path(cls.tmp.name)/'state')]:
                pp=patch.object(c,name,value);pp.start();cls.patchers.append(pp)
            # Provision actual AEs, ACPs and namespaces on the isolated CSEs.
            import access_control
            with patch.object(sys,'argv',['access_control.py','--apply']):access_control.main()
        except Exception:
            cls.tearDownClass();raise
    @classmethod
    def tearDownClass(cls):
        for pp in reversed(cls.patchers):pp.stop()
        for proc in cls.procs:
            proc.terminate()
            try:proc.wait(5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        for log in cls.logs:log.close()
        cls.tmp.cleanup()
    def test_typed_discovery_analysis_archive_dashboard_and_permissions(self):
        from sensor_simulator import SensorSimulator
        source=SensorSimulator(c.ROOT/'test_data_expanded.json','live-flex',c.COLLECTOR_ID)
        collector=Client(c.MN_URL,c.role_origin('collector'))
        samples=[source.read_measurements(i) for i in range(len(source))]
        for sample in samples:publish(collector,sample)
        reader=Client(c.MN_URL,c.role_origin('analyzer'))
        machines=list(discover_machines(reader,c.MN_BASE))
        self.assertGreaterEqual(len(machines),3)
        for machine in machines:
            latest=reader.latest(machine['path']+'/telemetry')
            typed=with_typed_readings(latest,machine)
            self.assertEqual(typed['data_model'],CND)
            self.assertEqual(typed['sensors'],latest['sensors'])
        state=State('live-analyzer')
        try:analyze_step(reader,state)
        finally:state.db.close()
        mn=Client(c.MN_URL,c.role_origin('forwarder'))
        central=Client(c.IN_URL,c.role_origin('forwarder'))
        state=State('live-forwarder')
        try:forward_step(mn,central,state)
        finally:state.db.close()
        view=dashboard.snapshot()
        self.assertGreaterEqual(len(view['machines']),3)
        self.assertTrue(all(m['telemetry']['data_model']==CND for m in view['machines']))
        self.assertTrue(all(m['analysis'] for m in view['machines']))
        target=machines[0]['path']+'/sensor-'+machines[0]['sensors'][0]['sensor_id']
        with self.assertRaises(OneM2MError) as raised:
            reader.call('PUT',target,{KIND:{'value':999}})
        self.assertEqual(raised.exception.status,403)
        target=list(discover_machines(Client(c.IN_URL,c.role_origin('dashboard')),c.IN_BASE+'/archive'))[0]
        with self.assertRaises(OneM2MError) as raised:
            Client(c.IN_URL,c.role_origin('dashboard')).call('PUT',target['path']+'/sensor-'+target['sensors'][0]['sensor_id'],{KIND:{'value':999}})
        self.assertEqual(raised.exception.status,403)

