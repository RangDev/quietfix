
import argparse
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
import requests
from transport_security import server_context,peer_name

def gateway(backend,cert,key,ca,bindings,host='127.0.0.1',port=0):
    target=urlsplit(backend)
    if target.scheme!='http' or target.hostname not in ('127.0.0.1','::1') or target.username or target.query or target.fragment:
        raise ValueError('Gateway backend must be an isolated loopback HTTP CSE')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def handle_request(self):
            try:
                identity=peer_name(self.connection)
                origin=self.headers.get('X-M2M-Origin','')
                if origin not in bindings.get(identity,[]):
                    self.send_error(403,'Certificate is not authorized for this Originator');return
                if not self.path.startswith('/') or self.path.startswith('//'):
                    self.send_error(400);return
                size=int(self.headers.get('Content-Length','0'))
                if not 0<=size<=1048576 or self.headers.get('Transfer-Encoding'):
                    self.send_error(400);return
                headers={k:v for k,v in self.headers.items() if k.lower().startswith('x-m2m-') or k.lower() in ('content-type','accept')}
                response=requests.request(self.command,backend.rstrip('/')+self.path,headers=headers,
                    data=self.rfile.read(size) if size else None,timeout=15,allow_redirects=False)
                self.send_response(response.status_code)
                for name in ('Content-Type','X-M2M-RSC','X-M2M-RI','X-M2M-RVI'):
                    if name in response.headers:self.send_header(name,response.headers[name])
                self.send_header('Content-Length',str(len(response.content)));self.end_headers();self.wfile.write(response.content)
            except (ValueError,ssl_error):self.send_error(400)
            except requests.RequestException:self.send_error(502)
        do_GET=do_POST=do_PUT=do_DELETE=handle_request
    import ssl
    ssl_error=ssl.SSLError
    server=ThreadingHTTPServer((host,port),Handler)
    server.socket=server_context(cert,key,ca).wrap_socket(server.socket,server_side=True)
    return server

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('backend','cert','key','ca','bindings'):p.add_argument('--'+flag,required=True)
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8443)
    a=p.parse_args()
    with open(a.bindings) as source:bindings=json.load(source)
    server=gateway(a.backend,a.cert,a.key,a.ca,bindings,a.host,a.port)
    try:server.serve_forever()
    finally:server.server_close()
if __name__=='__main__':main()

