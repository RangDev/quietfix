"""Explicit opt-in ACP provisioning. Never changes data or deletes resources."""
import argparse
from urllib.parse import urlencode
import config as c
from onem2m_client import Client

READ = 2 | 32  # RETRIEVE, DISCOVERY
CREATE, UPDATE, ALL = 1, 4, 63

def policy_ref(base, name):
    # Each gateway retains its own write policy when another is provisioned.
    if name in ('sensors', 'sensors-fcnt'):
        name += '-'+c.COLLECTOR_ID
    return base+'/qf-acp-'+name

def rule(origin, operations, children=None):
    value = {'acor': [origin], 'acop': operations}
    if children:
        value['acod'] = [{'chty': children}]
    return value

def policies():
    co, an, fw, db = (c.role_origin(r) for r in ('collector','analyzer','forwarder','dashboard'))
    if len({co, an, fw, db}) != 4:
        raise ValueError('Each runtime role must have a distinct origin')
    remote_fw = '/'+c.MN_CSE_ID+'/'+fw.lstrip('/')
    return {
        'sensors': [rule(co, READ), rule(co, CREATE, [3,4,28]),
                    rule(an, READ), rule(fw, READ),
                    rule(an, CREATE, [23]), rule(fw, CREATE, [23])],
        'sensors-fcnt': [rule(co, CREATE, [24]), rule(co, READ | UPDATE), rule(an, READ), rule(fw, READ)],
        'archive-fcnt': [rule(remote_fw, CREATE, [24]), rule(remote_fw, READ | UPDATE), rule(fw, CREATE, [24]), rule(fw, READ | UPDATE), rule(db, READ)],
        'analysis': [rule(an, READ), rule(an, CREATE, [4]),
                     rule(fw, READ), rule(fw, CREATE, [23])],
        'archive': [rule(remote_fw, READ), rule(remote_fw, CREATE, [3,4,9,28]), rule(fw, READ), rule(fw, CREATE, [3,4,9,28]), rule(db, READ)],
        'group': [rule(remote_fw, READ | UPDATE), rule(fw, READ | UPDATE), rule(db, READ)],
        'analyzer-sub': [rule(an, READ | UPDATE)],
        'forwarder-sub': [rule(fw, READ | UPDATE)],
        'identity': [rule(db, READ), rule(fw, READ)],
    }

def provision_policy(client, base, name, rules):
    # Runtime roles may reference/read ACPs, but only admin may modify them.
    readers = sorted({origin for r in rules for origin in r['acor']})
    attrs = {'rn': policy_ref(base,name).rsplit('/',1)[1],
             'pv': {'acr': [rule(c.ADMIN_ORIGIN, ALL), *rules]},
             'pvs': {'acr': [rule(c.ADMIN_ORIGIN, ALL), *[rule(o, 2) for o in readers]]}}
    client.ensure(base, 'm2m:acp', attrs, 1)
    client.call('PUT', policy_ref(base,name), {'m2m:acp': {k: attrs[k] for k in ('pv','pvs')}})

def attach(client, path, name, base):
    resource = client.call('GET', path)
    kind, attrs = next(iter(resource.items()))
    wanted = [policy_ref(base, name)]
    if attrs.get('acpi') != wanted:
        # oneM2M requires acpi to be the sole attribute of an UPDATE.
        # An AE without explicit ACPI can bootstrap it only as its owner.
        # Subsequent changes use the administrator granted by our PVS.
        owner = attrs.get('aei') if kind == 'm2m:ae' and not attrs.get('acpi') else None
        client.call('PUT', path, {kind: {'acpi': wanted}}, origin=owner)
    if kind == 'm2m:grp' and attrs.get('macp') != [policy_ref(base, 'group')]:
        client.call('PUT', path, {kind: {'macp': [policy_ref(base, 'group')]}})

def protect_tree(client, base, root, default):
    # CINs inherit access from their containers; do not mutate immutable CINs.
    attach(client, root, default, base)
    for ty in (3,9,23,28,24):
        query = urlencode({'fu':1,'ty':ty,'drt':1,'lim':10000})
        uris = client.call('GET', root+'?'+query).get('m2m:uril', [])
        if len(uris) >= 10000:
            raise RuntimeError('Discovery limit reached; migrate smaller subtrees before enabling ACP')
        for path in uris:
            name = 'group' if ty == 9 else default+'-fcnt' if ty in (24,28) else default
            if ty == 23:
                rn = next(iter(client.call('GET',path).values()))['rn']
                name = {'qf-analyzer':'analyzer-sub', 'qf-forwarder':'forwarder-sub'}.get(rn)
                if name is None:
                    raise RuntimeError('Review unknown subscription before migration: '+path)
            attach(client, path, name, base)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply ACPs to QuietFix resources on configured CSEs')
    args = parser.parse_args(argv)
    c.require_mn()
    if not args.apply:
        parser.error('Use --apply after reading ACP.md; this modifies resource permissions')
    # Force role configuration validation even if caller has not enabled runtime mode.
    c.ACP_ENABLED = True
    specs = policies()
    mn, central = Client(c.MN_URL,c.ADMIN_ORIGIN), Client(c.IN_URL,c.ADMIN_ORIGIN)
    from resource_registry import ensure_ae, ensure_analyzer, ensure_archive
    c.ACP_ENABLED = False
    try:
        for client,base,name,role in [(mn,c.MN_BASE,c.COLLECTOR_ID,'collector'),
                (mn,c.MN_BASE,'analyzer','analyzer'), (mn,c.MN_BASE,'forwarder','forwarder'),
                (central,c.IN_BASE,'archive','forwarder'), (central,c.IN_BASE,'dashboard','dashboard')]:
            ensure_ae(client,base,name)
            actual = client.call('GET',base+'/'+name)['m2m:ae']['aei']
            c.ACP_ENABLED = True
            expected = c.role_origin(role)
            c.ACP_ENABLED = False
            # archive AE is a storage namespace; forwarder registers separately on IN.
            if name != 'archive' and actual != expected:
                raise RuntimeError(f'{base}/{name}: AE-ID is {actual}; set QF_{role.upper()}_ORIGIN accordingly')
        ensure_ae(central,c.IN_BASE,'forwarder')
        actual = central.call('GET',c.IN_BASE+'/forwarder')['m2m:ae']['aei']
        c.ACP_ENABLED = True
        if actual != c.role_origin('forwarder'):
            raise RuntimeError('IN forwarder AE-ID differs; configure matching identity before continuing')
        c.ACP_ENABLED = False
        ensure_analyzer(mn)
        ensure_archive(central)
    finally:
        c.ACP_ENABLED = True
    for client,base,names in [(mn,c.MN_BASE,['sensors','sensors-fcnt','analysis','analyzer-sub','forwarder-sub','identity']),
                              (central,c.IN_BASE,['archive','archive-fcnt','group','identity'])]:
        for name in names:
            provision_policy(client,base,name,specs[name])
    protect_tree(mn,c.MN_BASE,c.MN_BASE+'/'+c.COLLECTOR_ID,'sensors')
    protect_tree(mn,c.MN_BASE,c.MN_BASE+'/analyzer','analysis')
    attach(mn,c.MN_BASE+'/forwarder','identity',c.MN_BASE)
    protect_tree(central,c.IN_BASE,c.IN_BASE+'/archive','archive')
    attach(central,c.IN_BASE+'/dashboard','identity',c.IN_BASE)
    attach(central,c.IN_BASE+'/forwarder','identity',c.IN_BASE)
    print('ACP applied. Start apps with QF_ACP_ENABLED=1. Run verify_access.py against live CSEs.')

if __name__ == '__main__':
    main()



def provision_backup_route(mn, central):
    """Admin-only provisioning; runtime backup never connects directly to IN."""
    from resource_registry import ensure_archive
    actual = mn.call('GET', c.MN_BASE)['m2m:cb']['csi'].strip('/')
    if actual != c.MN_CSE_ID:
        raise ValueError('QF_MN_CSE_ID must match the MN CSE-ID')
    ensure_archive(central)
    remote = '/'+actual+'/'+c.role_origin('forwarder').lstrip('/')
    for name in ('archive', 'archive-fcnt', 'group'):
        operations = READ | CREATE | UPDATE
        provision_policy(central, c.IN_BASE, name,
                         [rule(remote, operations), rule(c.role_origin('dashboard'), READ)])
    protect_tree(central, c.IN_BASE, c.IN_BASE+'/archive', 'archive')
