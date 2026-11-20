import argparse
import json
import os
from pathlib import Path
import secrets
import shlex
import signal
import subprocess
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'apps'))


def load_env(path):
    env = os.environ.copy()
    for line in path.read_text().splitlines():
        words = shlex.split(line, comments=True)
        if not words:
            continue
        if len(words) != 1 or '=' not in words[0]:
            raise ValueError('Expected KEY=value in node.env')
        key, value = words[0].split('=', 1)
        env[key] = value
    env['QF_STATE_DIR'] = str(ROOT / 'runtime/state')
    env['QF_ML_MODEL_DIR'] = str(ROOT / 'runtime/ml_models')
    env['PYTHONUNBUFFERED'] = '1'
    return env


def prepare(role, env):
    home = ROOT / 'runtime/cse'
    home.mkdir(parents=True, exist_ok=True)
    if role == 'collector':
        return
    import acmecse
    central = role == 'central'
    url = urlparse(env['QF_IN_URL' if central else 'QF_MN_URL'])
    registrar = urlparse(env['QF_IN_URL'])
    if url.scheme != 'http' or registrar.scheme != 'http':
        raise ValueError('This deployment profile requires HTTP on a trusted private network')
    base = env['QF_IN_BASE' if central else 'QF_MN_BASE']
    csi = env['QF_IN_CSE_ID' if central else 'QF_MN_CSE_ID'].strip('/')
    peer = env['QF_MN_CSE_ID' if central else 'QF_IN_CSE_ID'].strip('/')
    init = home / 'init'
    init.mkdir(exist_ok=True)
    import shutil
    shutil.copyfile(ROOT / 'models/quietfix.fcp', init / 'quietfix.fcp')
    path = home / 'acme.ini'
    if path.exists():
        raise ValueError('Configuration already exists; inspect/remove runtime/cse/acme.ini before preparing again')
    path.write_text(f'''[basic.config]
cseType={'IN' if central else 'MN'}
cseID={csi}
cseName={base}
adminID=CAdmin
cseHost={url.hostname}
httpPort={url.port or 80}
networkInterface={env.get('QF_CSE_BIND', '0.0.0.0')}
databaseType=tinydb
logLevel=info
consoleTheme=dark
consoleType=simple
registrarCseHost={'' if central else registrar.hostname}
registrarCseID={'' if central else env['QF_IN_CSE_ID'].strip('/')}
registrarCseName={'' if central else env['QF_IN_BASE']}
registrarCsePort={0 if central else registrar.port or 80}
secret={secrets.token_hex(32)}
serviceProviderID=//acme.example.com
[cse]
cseID=/{csi}
resourceID={csi}
resourceName={base}
originator=CAdmin
resourcesPath={Path(acmecse.__file__).parent / 'init'}
enableRemoteCSE=true
[cse.registration]
allowedCSROriginators=/{peer}
checkInterval=2
[cse.registrar]
INCSEcseID={env['QF_IN_CSE_ID']}
[http]
port={url.port or 80}
address={url.geturl()}
listenIF={env.get('QF_CSE_BIND', '0.0.0.0')}
[database]
type=tinydb
''')
    path.chmod(0o600)


def commands(role, env):
    home = ROOT / 'runtime/cse'
    cse = [sys.executable, '-m', 'acmecse', '--base-directory', str(home),
           '--headless', '--no-mqtt', '--no-coap', '--no-ws']
    app = lambda name: [sys.executable, str(ROOT / 'apps' / name)]
    if role == 'collector':
        return [(app('collector_ae.py') + ['--replay-id', env.get('QF_REPLAY_ID', 'distributed01')], ROOT)]
    if not (home / 'acme.ini').exists():
        raise ValueError('Run prepare first')
    if role == 'field':
        return [(cse, home), (app('analyzer_ae.py'), ROOT), (app('backup_ae.py'), ROOT)]
    return [(cse, home), (app('dashboard.py') + ['--host', env.get('QF_DASHBOARD_BIND', '0.0.0.0')], ROOT)]


def run(role, env):
    import fcntl
    runtime = ROOT / 'runtime'
    runtime.mkdir(exist_ok=True)
    processes = []
    with (runtime / 'run.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def interrupted(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupted)
        try:
            for command, cwd in commands(role, env):
                processes.append(subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True))
                if '-m' in command:
                    os.environ.update(env)
                    from onem2m_client import Client
                    central = role == 'central'
                    client = Client(env['QF_IN_URL' if central else 'QF_MN_URL'])
                    deadline = time.monotonic() + 45
                    while True:
                        if processes[-1].poll() is not None:
                            raise RuntimeError('CSE exited during startup')
                        try:
                            client.call('GET', env['QF_IN_BASE' if central else 'QF_MN_BASE'])
                            break
                        except Exception:
                            if time.monotonic() >= deadline:
                                raise RuntimeError('CSE readiness timeout')
                            time.sleep(.25)
            while all(p.poll() is None for p in processes):
                time.sleep(.5)
            raise RuntimeError('A managed process exited')
        except KeyboardInterrupt:
            pass
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()


def main():
    parser = argparse.ArgumentParser(description='Run this distributed deployment node')
    parser.add_argument('command', choices=['prepare', 'run', 'provision'])
    args = parser.parse_args()
    os.chdir(ROOT)
    role = json.loads((ROOT / 'role.json').read_text())['role']
    env = load_env(ROOT / 'node.env')
    if args.command == 'prepare':
        prepare(role, env)
    elif args.command == 'provision':
        if role != 'field':
            parser.error('Provision from the field node after both CSEs are running')
        subprocess.run([sys.executable, 'apps/setup_resources.py'], env=env, check=True)
    else:
        run(role, env)


if __name__ == '__main__':
    main()
