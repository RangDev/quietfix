"""Standalone loopback ACME deployment; no MEC, containers or Kubernetes."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps'))

def prepare(home):
    import acmecse
    home = home.resolve()
    home.mkdir(parents=True, exist_ok=True)
    for role, port, typ in [('in', 9090, 'IN'), ('mn', 8081, 'MN'), ('backup', 8082, 'MN')]:
        base = 'quietfix-' + role
        target = home / role
        target.mkdir(exist_ok=True)
        (target / 'init').mkdir(exist_ok=True)
        shutil.copyfile(ROOT/'models/quietfix.fcp', target/'init/quietfix.fcp')
        config = target / 'acme.ini'
        if config.exists():
            print('Preserved', config)
            continue
        config.write_text(f'''[basic.config]
cseType={typ}
cseID=id-{base}
cseName={base}
adminID=CAdmin
cseHost=127.0.0.1
httpPort={port}
networkInterface=127.0.0.1
databaseType=tinydb
logLevel=info
consoleTheme=dark
consoleType=simple
registrarCseHost={"127.0.0.1" if typ=="MN" else ""}
registrarCseID={"id-quietfix-in" if typ=="MN" else ""}
registrarCseName={"quietfix-in" if typ=="MN" else ""}
registrarCsePort={9090 if typ=="MN" else 0}
secret={secrets.token_hex(32)}
serviceProviderID=//acme.example.com
[cse]
cseID=/id-{base}
resourceID=id-{base}
resourceName={base}
originator=CAdmin
resourcesPath={Path(acmecse.__file__).parent/'init'}
enableRemoteCSE=true
[cse.registration]
allowedCSROriginators=/id-quietfix-mn,/id-quietfix-backup,/id-quietfix-in
checkInterval=2
[cse.registrar]
INCSEcseID=/id-quietfix-in
[http]
port={port}
address=http://127.0.0.1:{port}
listenIF=127.0.0.1
[database]
type=tinydb
''')
        config.chmod(0o600)
    env = home/'session.env'
    if not env.exists():
        import shlex
        values={'QF_MN_URL':'http://127.0.0.1:8081','QF_MN_BASE':'quietfix-mn',
                'QF_IN_URL':'http://127.0.0.1:9090','QF_IN_BASE':'quietfix-in',
                'QF_IN_CSE_ID':'/id-quietfix-in','QF_MN_CSE_ID':'/id-quietfix-mn',
                'QF_COLLECTOR_ID':'collector-01','QF_STATE_DIR':str(home/'state'),
                'QF_ANALYZER_NOTIFY_URL':'http://127.0.0.1:8091/notify',
                'QF_FORWARDER_NOTIFY_URL':'http://127.0.0.1:8092/notify',
                'QF_NOTIFY_HOST':'127.0.0.1','QF_ACP_ENABLED':'0',
                'QF_COLLECTOR_PROTOCOL':'http','QF_FLEX_ENABLED':'0','QF_SEMANTIC_ENABLED':'0'}
        env.write_text(''.join(f'export {key}={shlex.quote(value)}\n' for key,value in values.items()))
        env.chmod(0o600)
    print('Prepared', home, '\nSource', env, 'in each application shell.')

def check():
    from onem2m_client import Client
    central=Client('http://127.0.0.1:9090')
    for port,base,typ in [(9090,'quietfix-in',1),(8081,'quietfix-mn',2)]:
        value=Client(f'http://127.0.0.1:{port}').call('GET',base)['m2m:cb']
        if value['cst']!=typ:raise RuntimeError(f'Wrong CSE type: {base}')
    remote=Client('http://127.0.0.1:9090','/id-quietfix-mn/CAdmin').call('GET','~/id-quietfix-mn/quietfix-mn')['m2m:cb']
    if remote['csi']!='/id-quietfix-mn':raise RuntimeError('Remote CSE route mismatch')
    print('PASS: IN cst=1, MN cst=2 and IN -> Mcc -> MN remote retrieval')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','in','mn','backup','check'])
    p.add_argument('--home',type=Path,default=ROOT/'runtime/standalone')
    a=p.parse_args()
    if a.command=='prepare':prepare(a.home)
    elif a.command=='check':check()
    else:
        home=(a.home/a.command).resolve()
        if not (home/'acme.ini').exists():p.error('Run prepare first')
        os.chdir(home)
        raise SystemExit(subprocess.call([sys.executable,'-m','acmecse','--base-directory',str(home),
                           '--headless','--no-mqtt','--no-coap','--no-ws']))
if __name__=='__main__':main()

