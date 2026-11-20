
import argparse,json,os,time
from pathlib import Path
import config as c
import routing
from onem2m_client import Client
from resource_registry import discover_machines,publish,ensure_analyzer,register_machine
from access_control import main as provision,policy_ref
from flex_model import instant

def transfer(target_url,target_base,target_cse_id,target_mqtt_url=None):
    if not os.getenv('QF_ROUTE_FILE'):raise ValueError('QF_ROUTE_FILE must be shared by all MN workers')
    if not c.ACP_ENABLED:raise ValueError('Controlled handover requires ACP mode')
    started=time.monotonic();journal=os.environ['QF_ROUTE_FILE']+'.handover.json'
    with routing.route_lock(exclusive=True):
        source_route=routing.read_route()
        if (source_route['url'].rstrip('/'),source_route['base'].strip('/'))==(target_url.rstrip('/'),target_base.strip('/')):
            raise ValueError('Source and target must differ')
        if c.COLLECTOR_PROTOCOL=='mqtt' and (not target_cse_id or not target_mqtt_url):
            raise ValueError('MQTT target requires CSE-ID and broker URL')
        old=(c.MN_URL,c.MN_BASE,c.MQTT_CSE_ID,c.MQTT_URL)
        routing._controller=True
        report={'phase':'preparing','source':source_route,'target':{'url':target_url,'base':target_base,'cse_id':target_cse_id},'samples':0,'results':0}
        routing.atomic_write(journal,report)
        try:
            c.MN_URL=source_route['url'];c.MN_BASE=source_route['base'].strip('/')
            source=Client(c.MN_URL,c.ADMIN_ORIGIN)
            machines=list(discover_machines(source,c.MN_BASE))
            if any(m['collector_id']!=c.COLLECTOR_ID for m in machines):
                raise ValueError('This controller migrates one configured gateway; multiple gateways require coordinated migration')
            snapshots=[(m,list(source.records(m['path']+'/telemetry'))) for m in machines]
            catalogs=[source.latest(m['path']+'/metadata') for m in machines]
            results=list(source.records(ensure_analyzer(source)))
            subscriptions=[]
            parents=[m['path']+'/telemetry' for m in machines]+[c.MN_BASE+'/analyzer/results']
            for parent in parents:
                uris=source.call('GET',parent+'?fu=1&ty=23&drt=1&lim=10000').get('m2m:uril',[])
                if len(uris)>=10000:raise RuntimeError('Subscription discovery limit reached')
                for uri in uris:
                    sub=source.call('GET',uri)['m2m:sub']
                    if sub['rn'] not in ('qf-analyzer','qf-forwarder'):raise ValueError('Unknown subscription requires migration review')
                    subscriptions.append((parent,sub))
            source_base=c.MN_BASE
            c.MN_URL=target_url.rstrip('/');c.MN_BASE=target_base.strip('/')
            provision(['--apply'])
            target=Client(c.MN_URL,c.role_origin('collector'))
            targets=[]
            for machine,samples in snapshots:
                if not samples:raise ValueError('Cannot reconstruct a machine without retained telemetry')
                for sample in sorted(samples,key=lambda x:instant(x['timestamp'])):
                    path=publish(target,sample);targets.append((path,sample));report['samples']+=1
            for catalog in catalogs:register_machine(target,c.MN_BASE+'/'+c.COLLECTOR_ID,catalog)
            analyzer=Client(c.MN_URL,c.role_origin('analyzer'))
            result_path=ensure_analyzer(analyzer)
            for result in results:analyzer.put(result_path,result);report['results']+=1

            for path,sample in targets:
                import hashlib
                rn='qf-'+hashlib.sha256(sample['sample_id'].encode()).hexdigest()
                if analyzer.content(analyzer.call('GET',path+'/telemetry/'+rn)['m2m:cin'])!=sample:raise RuntimeError('Telemetry verification failed')
            actual={row['sample_id']:row for row in Client(c.MN_URL,c.role_origin('forwarder')).records(result_path)}
            if any(actual.get(row['sample_id'])!=row for row in results):raise RuntimeError('Analysis result verification failed')
            for parent,sub in subscriptions:
                relative=parent.lstrip('/')
                if not relative.startswith(source_base+'/'):raise ValueError('Unexpected subscription parent')
                destination=c.MN_BASE+relative[len(source_base):]
                role=sub['rn'][3:]
                attrs={k:sub[k] for k in ('rn','enc','nu','nct')}
                attrs['acpi']=[policy_ref(c.MN_BASE,role+'-sub')]
                client=Client(c.MN_URL,c.role_origin(role))
                existing=client.ensure(destination,'m2m:sub',attrs,23)['m2m:sub']
                if any(existing.get(k)!=attrs[k] for k in ('enc','nu','nct')):
                    client.call('PUT',destination+'/'+sub['rn'],{'m2m:sub':{k:attrs[k] for k in ('enc','nu','nct')}})
                checked=client.call('GET',destination+'/'+sub['rn'])['m2m:sub']
                if any(checked.get(k)!=attrs[k] for k in ('enc','nu','nct')):raise RuntimeError('Subscription verification failed')
            if c.COLLECTOR_PROTOCOL=='mqtt':
                from mqtt_client import MQTTClient
                c.MQTT_CSE_ID=target_cse_id;c.MQTT_URL=target_mqtt_url
                mqtt=MQTTClient(c.MN_URL,c.role_origin('collector'))
                try:mqtt.call('GET',c.MN_BASE+'/'+c.COLLECTOR_ID)
                finally:mqtt.close()
            report.update(phase='verified',subscriptions=len(subscriptions),missing_retained_samples=0)
            routing.atomic_write(journal,report)
            route={'url':c.MN_URL,'base':c.MN_BASE,'cse_id':target_cse_id}
            if target_mqtt_url:route['mqtt_url']=target_mqtt_url
            routing.atomic_write(os.environ['QF_ROUTE_FILE'],route)
            report.update(phase='committed',elapsed_seconds=time.monotonic()-started)
            routing.atomic_write(journal,report)
            return report
        except Exception as error:

            current=routing.read_route()
            report.update(phase='committed' if current!=source_route else 'failed_before_switch',error=str(error),elapsed_seconds=time.monotonic()-started)
            routing.atomic_write(journal,report)
            raise
        finally:
            c.MN_URL,c.MN_BASE,c.MQTT_CSE_ID,c.MQTT_URL=old
            routing._controller=False

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target-url',required=True);p.add_argument('--target-base',required=True)
    p.add_argument('--target-cse-id',required=True);p.add_argument('--target-mqtt-url')
    a=p.parse_args();print(json.dumps(transfer(a.target_url,a.target_base,a.target_cse_id,a.target_mqtt_url),indent=2))
if __name__=='__main__':main()

