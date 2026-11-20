import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'runtime/standalone'
BOOT_ID = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
ROLES = ('in', 'mn', 'analyzer', 'backup', 'dashboard', 'collector')


def environment():
    env = os.environ.copy()
    for line in (HOME / 'session.env').read_text().splitlines():
        words = shlex.split(line, comments=True)
        if not words:
            continue
        if len(words) != 2 or words[0] != 'export' or '=' not in words[1]:
            raise ValueError('Expected export KEY=value in session.env')
        key, value = words[1].split('=', 1)
        env[key] = value
    env['PYTHONUNBUFFERED'] = '1'
    return env


def alive(record):
    try:
        fields = Path(f"/proc/{record['pid']}/stat").read_text().rsplit(')', 1)[1].split()
        return fields[0] != 'Z' and fields[19] == record['started'] and record['boot_id'] == BOOT_ID
    except (OSError, KeyError):
        return False


def stop(records):
    for role in reversed(ROLES):
        record = records.get(role)
        if not record or not alive(record):
            continue
        os.killpg(record['pid'], signal.SIGINT)
        deadline = time.monotonic() + 15
        while alive(record) and time.monotonic() < deadline:
            time.sleep(.1)
        if alive(record):
            os.killpg(record['pid'], signal.SIGTERM)
            deadline = time.monotonic() + 5
            while alive(record) and time.monotonic() < deadline:
                time.sleep(.1)
        if alive(record):
            os.killpg(record['pid'], signal.SIGKILL)
        print('STOPPED', role)


def wait_for(check, processes, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for role, process in processes.items():
            if process.poll() is not None:
                raise RuntimeError(f'{role} exited; see runtime/standalone/logs/{role}.log')
        try:
            if check():
                return
        except (OSError, ValueError):
            pass
        time.sleep(.25)
    raise RuntimeError('Readiness timeout; inspect service logs')


def http_ready(url):
    request = urllib.request.Request(url, headers={'X-M2M-Origin': 'CAdmin', 'X-M2M-RI': str(time.time_ns()), 'X-M2M-RVI': '3'})
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.status == 200


def start(args, records, save):
    if any(alive(record) for record in records.values()):
        raise RuntimeError('Managed services already running; use status or stop first')
    for port in (9090, 8081, 8090, 8091, 8092):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))
    env = environment()
    if args.dataset and not Path(args.dataset).is_file():
        raise ValueError('Dataset does not exist')
    logs = HOME / 'logs'
    logs.mkdir(exist_ok=True)
    records.clear()
    processes = {}
    try:
        for role in ROLES:
            if role in ('in', 'mn'):
                command = ['standalone/manage.py', role]
            else:
                command = [f'apps/{role}_ae.py' if role != 'dashboard' else 'apps/dashboard.py']
            if role == 'collector':
                command += ['--replay-id', args.replay_id]
                if args.dataset:
                    command += ['--dataset', str(Path(args.dataset).resolve()), '--mode', 'replay', '--interval', str(args.interval)]
            with (logs / f'{role}.log').open('a') as log:
                process = subprocess.Popen([sys.executable, *command], cwd=ROOT, env=env,
                                           stdout=log, stderr=log, start_new_session=True)
            processes[role] = process
            fields = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()
            records[role] = {'pid': process.pid, 'started': fields[19], 'boot_id': BOOT_ID}
            save()
            if role in ('in', 'mn'):
                port = 9090 if role == 'in' else 8081
                wait_for(lambda: http_ready(f'http://127.0.0.1:{port}/quietfix-{role}'), processes)
                if role == 'mn':
                    wait_for(lambda: subprocess.run([sys.executable, 'standalone/manage.py', 'check'],
                        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0, processes)
                    subprocess.run([sys.executable, 'apps/setup_resources.py'], cwd=ROOT, env=env, check=True, timeout=60)
            elif role == 'dashboard':
                wait_for(lambda: http_ready('http://127.0.0.1:8090/'), processes)
        wait_for(lambda: http_ready('http://127.0.0.1:8090/api'), processes, timeout=60)
        print('RUNNING http://127.0.0.1:8090/ (use /api to inspect analysis and model_state)')
    except BaseException:
        stop(records)
        records.clear()
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description='Manage the local Linux HTTP deployment')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'logs'])
    parser.add_argument('--service', choices=ROLES)
    parser.add_argument('--dataset')
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--replay-id', default='managed01')
    args = parser.parse_args()
    os.chdir(ROOT)
    HOME.mkdir(parents=True, exist_ok=True)
    with (HOME / 'service.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = HOME / 'services.json'
        records = json.loads(manifest.read_text()) if manifest.exists() else {}
        def save():
            temp = manifest.with_suffix('.tmp')
            temp.write_text(json.dumps(records, indent=2))
            temp.replace(manifest)
        if args.command == 'start':
            start(args, records, save)
        elif args.command == 'stop':
            stop(records)
            records.clear()
            save()
        elif args.command == 'status':
            for role in ROLES:
                print(role, 'RUNNING' if alive(records.get(role, {})) else 'STOPPED')
            return 0 if all(alive(records.get(role, {})) for role in ROLES) else 1
        else:
            for role in ([args.service] if args.service else ROLES):
                path = HOME / 'logs' / f'{role}.log'
                print(f'[{role}]')
                print('\n'.join(path.read_text(errors='replace').splitlines()[-30:]) if path.exists() else 'No log yet')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
