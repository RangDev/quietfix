"""Actual standalone ACME smoke test. Stop existing listeners on 8081/9090 first."""
import subprocess,sys,time,os,tempfile,json,signal,socket
from unittest.mock import patch
import requests
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0,str(ROOT/'apps'))
from onem2m_client import Client
for port in (8081,9090):
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',port))
        except OSError:raise SystemExit(f'Port {port} is busy. Stop existing CSEs before smoke testing.')
tmp=tempfile.TemporaryDirectory(prefix="qf-standalone-")
home=Path(tmp.name)
subprocess.run([sys.executable,"standalone/manage.py","prepare","--home",str(home)],check=True)
procs=[]
try:
 for role,port in [('in',9090),('mn',8081)]:
  log=open(home/(role+'-smoke.log'),'w')
  procs.append(subprocess.Popen([sys.executable,'standalone/manage.py',role,'--home',str(home)],stdout=log,stderr=log,start_new_session=True))
  for i in range(120):
   try:Client(f'http://127.0.0.1:{port}').call('GET','quietfix-'+role);break
   except Exception:
    if procs[-1].poll() is not None:raise RuntimeError(Path(log.name).read_text())
    time.sleep(.25)
  else:raise RuntimeError('startup timeout '+role)
 for i in range(4):
  r=subprocess.run([sys.executable,'standalone/manage.py','check'],capture_output=True,text=True,timeout=8)
  if r.returncode==0:print(r.stdout);break
  time.sleep(.5)
 else:raise RuntimeError(r.stderr)
 import config as c
 c.MN_BASE='quietfix-mn';c.IN_BASE='quietfix-in'
 from sensor_simulator import SensorSimulator
 from resource_registry import publish
 from analyzer_ae import step as analyze
 from backup_ae import step as forward
 from onem2m_client import ArchiveViaMN
 from worker_state import State
 c.STATE=home/'state'
 from adaptive_collector import Timeline
 rows=Timeline('test_data/test_data_timeline.json').read(0)
 dataset=home/'samples.json';dataset.write_text(json.dumps(rows))
 source=SensorSimulator(dataset,'standalone-smoke')
 mn=Client('http://127.0.0.1:8081');central=Client('http://127.0.0.1:9090')
 for i in range(len(source)):publish(mn,source.read_measurements(i))
 from access_control import provision_backup_route
 provision_backup_route(mn,central)
 analyze(mn,State('analyzer'))
 routed = ArchiveViaMN(mn)
 request = requests.request
 def mn_only(method,url,**kwargs):
  assert url.startswith(mn.url+'/'), 'Backup AE contacted a non-MN endpoint: '+url
  return request(method,url,**kwargs)
 with patch('requests.request',side_effect=mn_only):
  forward(mn,routed,State('forwarder'))
  forward(mn,routed,State('forwarder'))  # retry/restart is idempotent
 from access_control import main as apply_acp
 apply_acp(['--apply'])
 secure_mn=Client(mn.url,c.role_origin('forwarder'))
 with patch('requests.request',side_effect=mn_only):
  forward(secure_mn,ArchiveViaMN(secure_mn),State('secure-backup'))
 group=central.call('GET',c.IN_BASE+'/archive/telemetryGroup')['m2m:grp']
 assert len(group['mid'])==8
 for machine in __import__('resource_registry').discover_machines(Client(mn.url),c.MN_BASE):
  source_path=machine['path']+'/telemetry'
  target_path=c.IN_BASE+'/archive/'+machine['collector_id']+'/machine-'+machine['machine_id']+'/telemetry'
  assert list(Client(mn.url).records(source_path))==list(central.records(target_path))
 print('PASS backup MN-only HTTP, Mcc archive equality, restart deduplication, group and role ACP')
 from dashboard import snapshot
 assert len(snapshot()['machines'])==8
 print('PASS real ACME publish -> analysis -> archive -> dashboard (8-machine default timeline)')
finally:
 for p in reversed(procs):
  os.killpg(p.pid,signal.SIGTERM)
  try:p.wait(10)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()

 tmp.cleanup()

