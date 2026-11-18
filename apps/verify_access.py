"""Live CSE permission checks using temporary containers; no existing CIN edits."""
import argparse
import uuid
import config as c
from access_control import policy_ref, policies
from onem2m_client import Client, OneM2MError

def denied(client, method, path, body, ty=None):
    try:
        client.call(method,path,body,ty)
    except OneM2MError as error:
        if error.status != 403:
            raise AssertionError(f'Expected permission denial, got HTTP {error.status}') from error
    else:
        raise AssertionError('Forbidden request succeeded: '+method+' '+path)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',action='store_true',help='Create and clean temporary test containers')
    if not p.parse_args().run:
        p.error('Use --run after applying access_control.py --apply')
    c.require_mn()
    c.ACP_ENABLED=True
    policies()  # Validate distinct non-admin role origins.
    checks=0
    for url,base,parent,policy,writer,readers,forbidden in [
        (c.MN_URL,c.MN_BASE,c.MN_BASE+'/'+c.COLLECTOR_ID,'sensors','collector',('analyzer','forwarder'),('analyzer','forwarder')),
        (c.MN_URL,c.MN_BASE,c.MN_BASE+'/analyzer','analysis','analyzer',('forwarder',),('collector',)),
        (c.IN_URL,c.IN_BASE,c.IN_BASE+'/archive','archive','forwarder',('dashboard',),('dashboard',))]:
        admin=Client(url,c.ADMIN_ORIGIN)
        name='qf-acp-check-'+uuid.uuid4().hex
        path=parent+'/'+name
        admin.call('POST',parent,{'m2m:cnt':{'rn':name,'acpi':[policy_ref(base,policy)],'mni':10}},3)
        try:
            body={'m2m:cin':{'rn':'probe','con':'ACP permission probe'}}
            Client(url,c.role_origin(writer)).call('POST',path,body,4);checks+=1
            for role in readers:
                Client(url,c.role_origin(role)).call('GET',path+'/probe');checks+=1
            for role in forbidden:
                denied(Client(url,c.role_origin(role)),'POST',path,{'m2m:cin':{'rn':'forbidden-'+role,'con':'must be rejected'}},4);checks+=1
            role=readers[0]
            denied(Client(url,c.role_origin(role)),'DELETE',path,None);checks+=1
            # A non-admin must not change policy definitions or resource ACPI.
            client=Client(url,c.role_origin(writer))
            denied(client,'PUT',policy_ref(base,policy),{'m2m:acp':{'pv':{'acr':[{'acor':['*'],'acop':63}]}}});checks+=1
            denied(client,'PUT',path,{'m2m:cnt':{'acpi':[policy_ref(base,policy)]}});checks+=1
        finally:
            admin.call('DELETE',path)
    print(f'PASS: {checks} live permission checks. Temporary containers removed.')
    print('Also verify notification delivery, subscription URL updates, group fan-out, and dynamic machine registration with running apps.')

if __name__=='__main__':main()
