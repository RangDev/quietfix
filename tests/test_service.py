import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('service', Path(__file__).resolve().parents[1] / 'standalone/service.py')
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)


class ServiceState(unittest.TestCase):
    def test_process_identity_and_reboot(self):
        pid = os.getpid()
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        record = dict(pid=pid, started=fields[19], boot_id=service.BOOT_ID)
        self.assertTrue(service.alive(record))
        self.assertFalse(service.alive({**record, 'started': 'invalid'}))
        self.assertFalse(service.alive({**record, 'boot_id': 'previous-boot'}))
        self.assertFalse(service.alive({}))

    def test_environment_is_parsed_without_shell_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / 'session.env').write_text("export QF_STATE_DIR='/tmp/space here'\nexport QF_COLLECTOR_ID='$(exit 12)'\n")
            with patch.object(service, 'HOME', home):
                env = service.environment()
            self.assertEqual(env['QF_STATE_DIR'], '/tmp/space here')
            self.assertEqual(env['QF_COLLECTOR_ID'], '$(exit 12)')
            (home / 'session.env').write_text('source another.env\n')
            with patch.object(service, 'HOME', home), self.assertRaises(ValueError):
                service.environment()


if __name__ == '__main__':
    unittest.main()
