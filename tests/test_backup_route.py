
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'apps'))
import config as c
from onem2m_client import Client, ArchiveViaMN

class BackupRoute(unittest.TestCase):
    def test_remote_target_and_current_mn_endpoint(self):
        mn=Client('http://mn:8081','Cqfforwarder')
        routed=ArchiveViaMN(mn)
        urls=[]
        def request(method,url,**kwargs):
            urls.append(url)
            self.assertEqual(kwargs['headers']['X-M2M-Origin'],'Cqfforwarder')
            class Response:
                ok=True
                headers={}
                content=b'{}'
                def json(self):return {}
            return Response()
        with patch.multiple(c,IN_BASE='in',IN_CSE_ID='id-in'), patch('requests.request',side_effect=request):
            routed.call('GET','in/archive')
            mn.url='http://replacement:8082'
            routed.call('GET','/id-in/in/archive?fu=1')
            self.assertEqual(urls,['http://mn:8081/~/id-in/in/archive',
                                  'http://replacement:8082/~/id-in/in/archive?fu=1'])
            with self.assertRaises(ValueError):routed.call('GET','other/archive')

    def test_backup_failure_does_not_advance_checkpoint(self):
        from backup_ae import step
        from unittest.mock import Mock
        sample={'sample_id':'s'}
        mn=Mock();mn.records.return_value=[sample]
        central=Mock();central.put.side_effect=TimeoutError('lost response')
        state=Mock();state.has.return_value=False
        with patch('backup_ae.ensure_archive',return_value='in/archive/results'), \
             patch('backup_ae.discover_machines',return_value=[]), \
             patch('backup_ae.ensure_analyzer',return_value='mn/analyzer/results'):
            with self.assertRaises(TimeoutError):step(mn,central,state)
            state.mark.assert_not_called()
            central.put.side_effect=None
            step(mn,central,state)
            state.mark.assert_called_once_with('v3:mn/analyzer/results:s')

if __name__=='__main__':unittest.main()

