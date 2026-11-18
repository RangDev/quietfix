"""Maintain an IN telemetry group and retrieve its latest CINs."""
import config as c
from onem2m_client import OneM2MError
from resource_registry import discover_machines

def sync_group(client):
    members = sorted(m['path'].lstrip('/')+'/telemetry' for m in discover_machines(client, c.IN_BASE+'/archive'))
    if not members:
        return
    attrs = {'rn': 'telemetryGroup', 'mt': 3, 'mnm': max(1000,len(members)), 'mid': members}
    if c.ACP_ENABLED:
        from access_control import policy_ref
        attrs['acpi'] = [policy_ref(c.IN_BASE, 'group')]
        attrs['macp'] = [policy_ref(c.IN_BASE, 'group')]
    path = c.IN_BASE+'/archive/telemetryGroup'
    current = client.ensure(c.IN_BASE+'/archive', 'm2m:grp', attrs, 9)['m2m:grp']
    if sorted(current.get('mid', [])) != members:
        client.call('PUT', path, {'m2m:grp': {'mid': members, 'mnm': attrs['mnm']}})

def latest_group(client):
    try:
        result = client.call('GET', c.IN_BASE+'/archive/telemetryGroup/fopt/la')
    except OneM2MError as e:
        if e.status not in (400,404,405,501):
            raise
        return {}
    readings = {}
    responses = result.get('m2m:agr', {}).get('m2m:rsp', [])
    if isinstance(responses, dict):
        responses = [responses]
    for response in responses:
        if int(response.get('rsc', 0)) != 2000:
            continue
        cin = response.get('pc', {}).get('m2m:cin')
        if cin is not None:
            sample = client.content(cin)
            readings[(sample['collector_id'],sample['machine_id'])] = sample
    return readings
