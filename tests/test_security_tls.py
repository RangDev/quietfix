import json,sys,tempfile,threading,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps'))
import requests
from secure_gateway import gateway
from tls_fixture import certificates

class TLSIntegration(unittest.TestCase):
    def test_real_mtls_origin_binding_and_certificate_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=certificates(tmp)
            class Backend(BaseHTTPRequestHandler):
                def log_message(self,*a):pass
                def do_GET(self):
                    data=json.dumps({'origin':self.headers['X-M2M-Origin']}).encode()
                    self.send_response(200);self.end_headers();self.wfile.write(data)
            backend=ThreadingHTTPServer(('127.0.0.1',0),Backend)
            server=gateway('http://127.0.0.1:'+str(backend.server_port),root/'server.crt',root/'server.key',root/'ca.crt',{'collector':['Cqfcollector-01'],'dashboard':['Cqfdashboard']})
            threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (backend,server)]
            for thread in threads:thread.start()
            url='https://localhost:'+str(server.server_port)+'/mn'
            options={'verify':str(root/'ca.crt'),'cert':(str(root/'collector.crt'),str(root/'collector.key')),'timeout':3}
            try:
                good=requests.get(url,headers={'X-M2M-Origin':'Cqfcollector-01'},**options)
                self.assertEqual(good.json()['origin'],'Cqfcollector-01')
                self.assertEqual(requests.get(url,headers={'X-M2M-Origin':'CAdmin'},**options).status_code,403)
                options['cert']=(str(root/'rogue.crt'),str(root/'rogue.key'))
                self.assertEqual(requests.get(url,headers={'X-M2M-Origin':'Cqfcollector-01'},**options).status_code,403)
                with self.assertRaises(requests.exceptions.SSLError):requests.get(url,verify=str(root/'ca.crt'),timeout=3)
                with self.assertRaises(requests.exceptions.SSLError):requests.get(url,cert=options['cert'],timeout=3)
            finally:
                for s in (server,backend):s.shutdown();s.server_close()
                for thread in threads:thread.join()
