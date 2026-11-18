"""Versioned typed sensor projection with real FCNT discovery (ty=28, cnd)."""
from datetime import datetime
from urllib.parse import urlencode
import config as c
from device_model import identifier, normalize

KIND = 'qf:sensorReading'
CND = 'org.quietfix.sensorReading.v1'
LABEL = 'quietfix-sensor-v1'

def instant(value):
    stamp = datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Sensor timestamps must include a time zone')
    return stamp

def publish_readings(client, machine_path, sample):
    sample = normalize(sample)
    instant(sample['timestamp'])
    for sensor in sample['sensors']:
        rn = 'sensor-'+identifier(sensor['sensor_id'])
        attrs = {'rn':rn, 'cnd':CND, 'lbl':[LABEL],
                 'sensorId':sensor['sensor_id'], 'sensorType':sensor['type'],
                 'label':sensor['label'], 'unit':sensor['unit'], 'value':sensor['value'],
                 'sampleId':sample['sample_id'], 'timestamp':sample['timestamp'],
                 'collectorId':sample['collector_id'], 'machineId':sample['machine_id'],
                 'machineName':sample['machine_name']}
        if c.ACP_ENABLED:
            from access_control import policy_ref
            archive = machine_path.startswith(c.IN_BASE+'/archive/')
            attrs['acpi']=[policy_ref(c.IN_BASE if archive else c.MN_BASE,
                                      'archive-fcnt' if archive else 'sensors-fcnt')]
        existing = client.ensure(machine_path, KIND, attrs, 28)[KIND]
        if existing.get('cnd') != CND:
            raise ValueError('Unexpected sensor specialization at '+machine_path+'/'+rn)
        # Historical catch-up/retry must not move the latest-value projection backwards.
        if instant(existing['timestamp']) > instant(sample['timestamp']):
            continue
        changes = {k:v for k,v in attrs.items() if k not in ('rn','cnd','lbl','acpi')}
        if any(existing.get(k) != v for k,v in changes.items()):
            client.call('PUT', machine_path+'/'+rn, {KIND:changes})
        if c.SEMANTIC_ENABLED:
            from semantics import publish_descriptor
            publish_descriptor(client,machine_path+'/'+rn,attrs)

def discover(client, base):
    query=urlencode({'fu':1, 'ty':28, 'cnd':CND, 'lbl':LABEL, 'drt':1, 'lim':10000})
    if c.SEMANTIC_ENABLED:
        from semantics import discover_paths
        uris=discover_paths(client,base)
    else:
        uris=client.call('GET',base+'?'+query).get('m2m:uril',[])
    if len(uris)>=10000:
        raise RuntimeError('FCNT discovery limit reached; use a smaller subtree')
    machines={}
    for uri in sorted(uris):
        attrs=client.call('GET',uri)[KIND]
        if attrs.get('cnd') != CND:
            raise ValueError('Unexpected FCNT model returned by discovery')
        path=uri.rsplit('/',1)[0]
        collector,machine=identifier(attrs['collectorId']),identifier(attrs['machineId'])
        sensor={'sensor_id':identifier(attrs['sensorId']), 'type':attrs['sensorType'],
                'label':attrs['label'],'unit':attrs['unit'],'value':attrs['value']}
        normalize({'machine_id':machine,'sensors':[sensor]})
        entry=machines.setdefault(path, {'path':path,'collector_id':collector,'machine_id':machine,
            'machine_name':attrs['machineName'],'sensors':[],'_typed':[]})
        if (entry['collector_id'],entry['machine_id'])!=(collector,machine):
            raise ValueError('Conflicting machine identities in typed readings')
        entry['sensors'].append({k:v for k,v in sensor.items() if k!='value'})
        entry['_typed'].append((attrs,sensor))
    yield from (machines[k] for k in sorted(machines))

def with_typed_readings(sample, machine):
    """Use a complete matching typed snapshot; history/partial updates stay on CIN."""
    readings=[s for attrs,s in machine.get('_typed',[]) if
              attrs['sampleId']==sample['sample_id'] and attrs['timestamp']==sample['timestamp'] and
              attrs['collectorId']==sample['collector_id'] and attrs['machineId']==sample['machine_id']]
    expected={s['sensor_id'] for s in normalize(sample)['sensors']}
    if len(readings)==len(expected) and {s['sensor_id'] for s in readings}==expected:
        by_id={s['sensor_id']:s for s in readings}
        ordered=[by_id[s['sensor_id']] for s in normalize(sample)['sensors']]
        return {**sample,'sensors':ordered,'data_model':CND}
    return sample
