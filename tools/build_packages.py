import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def copy_tree(source, target):
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(
        '__pycache__', '*.pyc', 'state', 'runtime', 'local', '.env*',
        '*.sqlite*', '*.joblib', '*.pem', '*.key', '*.crt', '*.log'))


def build(output):
    output = Path(output).resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output.is_relative_to(ROOT / 'apps'):
        raise ValueError('Output must be a dedicated package directory')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; choose a new directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary)
        single = stage / 'single-vm'
        single.mkdir()
        for name in ('apps', 'models', 'test_data', 'standalone', 'security', 'docs'):
            copy_tree(ROOT / name, single / name)
        shutil.copyfile(ROOT / 'deploy/single-vm.md', single / 'README.md')
        for role in ('collector', 'field', 'central'):
            target = stage / 'distributed' / role
            target.mkdir(parents=True)
            for name in ('apps', 'models', 'test_data', 'security'):
                copy_tree(ROOT / name, target / name)
            shutil.copyfile(ROOT / 'standalone/requirements-lock.txt', target / 'requirements.txt')
            shutil.copyfile(ROOT / 'deploy/distributed/run.py', target / 'run.py')
            shutil.copyfile(ROOT / 'deploy/distributed/README.md', target / 'README.md')
            shutil.copyfile(ROOT / f'deploy/distributed/{role}.env.example', target / 'node.env.example')
            (target / 'role.json').write_text(json.dumps({'role': role}) + '\n')
        shutil.copyfile(ROOT / 'deploy/distributed/README.md', stage / 'distributed/README.md')
        manifest = {}
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                manifest[str(path.relative_to(stage))] = hashlib.sha256(path.read_bytes()).hexdigest()
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        output.mkdir(exist_ok=True)
        for path in stage.iterdir():
            shutil.move(str(path), output / path.name)
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build independent deployment packages from source')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    build(parser.parse_args().output)
