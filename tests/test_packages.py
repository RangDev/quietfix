import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_builder', ROOT / 'tools/build_packages.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class Packages(unittest.TestCase):
    def test_independent_packages_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'packages'
            builder.build(output)
            manifest = json.loads((output / 'manifest.json').read_text())
            for name, digest in manifest.items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            for role in ('collector', 'field', 'central'):
                node = output / 'distributed' / role
                self.assertEqual(json.loads((node / 'role.json').read_text())['role'], role)
                subprocess.run([sys.executable, 'run.py', '--help'], cwd=node, check=True,
                               stdout=subprocess.DEVNULL)
                (node / 'node.env').write_text((node / 'node.env.example').read_text())
                subprocess.run([sys.executable, 'run.py', 'prepare'], cwd=node, check=True)
                if role != 'collector':
                    config = (node / 'runtime/cse/acme.ini').read_text()
                    self.assertIn('networkInterface=0.0.0.0', config)
                    self.assertIn('cseType=' + ('IN' if role == 'central' else 'MN'), config)
                    result = subprocess.run([sys.executable, 'run.py', 'prepare'], cwd=node,
                                            capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
            subprocess.run([sys.executable, 'standalone/manage.py', '--help'],
                           cwd=output / 'single-vm', check=True, stdout=subprocess.DEVNULL)
            with self.assertRaises(ValueError):
                builder.build(output)

    def test_copy_excludes_runtime_and_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            for name in ('runtime', 'state', 'local', '__pycache__'):
                (source / name).mkdir()
                (source / name / 'secret').write_text('private')
            for name in ('.env', 'client.key', 'client.pem', 'model.joblib', 'db.sqlite3'):
                (source / name).write_text('private')
            (source / 'config.py').write_text('value = 1\n')
            target = Path(tmp) / 'target'
            builder.copy_tree(source, target)
            self.assertEqual([p.name for p in target.iterdir()], ['config.py'])
