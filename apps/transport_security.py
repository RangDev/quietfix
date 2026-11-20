
import json
import os
import ssl

def http_options(origin):
    ca=os.getenv('QF_HTTP_CA_FILE')
    raw=os.getenv('QF_HTTP_IDENTITIES_FILE')
    if not raw:return {'verify':ca or os.getenv('QF_LOCAL_INSECURE')!='1'}
    with open(raw) as source:identities=json.load(source)
    if origin not in identities:raise ValueError('No HTTP client certificate for requested Originator')
    identity=identities[origin]
    if not ca:raise ValueError('QF_HTTP_CA_FILE is required with HTTP identities')
    return {'verify':ca,'cert':(identity['cert'],identity['key'])}

def server_context(cert,key,ca):
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert,key)
    context.load_verify_locations(ca)
    context.verify_mode=ssl.CERT_REQUIRED
    return context

def peer_name(connection):
    names=[value for group in connection.getpeercert().get('subject',[]) for name,value in group if name=='commonName']
    if len(names)!=1:raise ValueError('Expected one certificate commonName')
    return names[0]

