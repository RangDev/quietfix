"""SAREF 3.1.1 measurements with explicit local extensions and QUDT units."""
import base64
import math
from urllib.parse import urlencode,quote
from rdflib import Graph,Namespace,URIRef,Literal,RDF,XSD
SAREF=Namespace('https://saref.etsi.org/core/')
QF=Namespace('https://quietfix.example/ontology/')
UNIT=Namespace('http://qudt.org/vocab/unit/')
PROPERTIES={'temperature':SAREF.Temperature,'vibration_rms':QF.VibrationRMS,'current':QF.ElectricCurrent}
UNITS={'°C':UNIT.DEG_C,'mm/s':UNIT['MilliM-PER-SEC'],'A':UNIT.A}
ALIASES={'temp':'temperature','temperature':'temperature','vibration_rms':'vibration_rms','vibration':'vibration_rms','current':'current','ampere':'current'}

def canonical(sensor):
    result=dict(sensor);kind=ALIASES.get(sensor.get('type'))
    if not kind:return result
    unit=sensor.get('unit');value=sensor['value']
    if kind=='temperature':
        if unit in ('°C','Celsius','degC'):unit='°C'
        elif unit in ('°F','Fahrenheit'):value=(value-32)*5/9;unit='°C'
        elif unit in ('K','kelvin'):value=value-273.15;unit='°C'
    elif kind=='current':
        if unit=='mA':value=value/1000;unit='A'
        elif unit=='ampere':unit='A'
    elif kind=='vibration_rms' and unit=='m/s':value=value*1000;unit='mm/s'
    result.update(type=kind,unit=unit,value=value)
    return result

def descriptor(path,attrs):
    graph=Graph();graph.bind('saref',SAREF);graph.bind('qf',QF)
    sensor=URIRef('urn:quietfix:sensor:'+attrs['collectorId']+':'+attrs['machineId']+':'+attrs['sensorId'])
    measurement=URIRef(str(sensor)+':measurement');prop=URIRef(str(sensor)+':property')
    kind=PROPERTIES.get(attrs['sensorType'],QF['property/'+quote(attrs['sensorType'],safe='')])
    unit=UNITS.get(attrs['unit'],QF['unit/'+quote(attrs['unit'],safe='')])
    graph.add((sensor,RDF.type,SAREF.Sensor));graph.add((sensor,QF.resourcePath,Literal(path)))
    graph.add((sensor,SAREF.makesMeasurement,measurement));graph.add((measurement,RDF.type,SAREF.Measurement))
    graph.add((measurement,SAREF.relatesToProperty,prop));graph.add((prop,RDF.type,kind))
    graph.add((measurement,SAREF.hasValue,Literal(attrs['value'],datatype=XSD.double)))
    graph.add((measurement,SAREF.isMeasuredIn,unit));graph.add((measurement,SAREF.hasTimestamp,Literal(attrs['timestamp'],datatype=XSD.dateTime)))
    return base64.b64encode(graph.serialize(format='xml').encode()).decode()

def publish_descriptor(client,path,attrs):
    dsp=descriptor(path,attrs)
    if dsp is None:return
    body={'rn':'meaning','dcrp':4,'dsp':dsp}
    if attrs.get('acpi'):body['acpi']=attrs['acpi']
    old=client.ensure(path,'m2m:smd',body,24)['m2m:smd']
    if old.get('dsp')!=dsp:client.call('PUT',path+'/meaning',{'m2m:smd':{'dsp':dsp}})

def discover_paths(client,base,property_type=None):
    # Server discovers SMD resources; RDF matching is an explicit client SPARQL query.
    uris=client.call('GET',base+'?'+urlencode({'fu':1,'ty':24,'drt':1,'lim':10000})).get('m2m:uril',[])
    if len(uris)>=10000:raise RuntimeError('Semantic discovery limit reached')
    graph=Graph()
    for uri in uris:
        attrs=client.call('GET',uri)['m2m:smd']
        if attrs.get('dcrp')!=4:continue
        data=base64.b64decode(attrs['dsp'],validate=True)
        if len(data)>1048576 or b'<!DOCTYPE' in data.upper():raise ValueError('Unsafe semantic descriptor')
        graph.parse(data=data,format='xml')
    kinds=[PROPERTIES[property_type]] if property_type else []
    values=' '.join('<'+str(kind)+'>' for kind in kinds)
    clause='VALUES ?kind { '+values+' }' if kinds else ''
    query='''SELECT DISTINCT ?path WHERE {
      ?sensor <https://quietfix.example/ontology/resourcePath> ?path ;
              <https://saref.etsi.org/core/makesMeasurement> ?m .
      ?m <https://saref.etsi.org/core/relatesToProperty> ?p .
      ?p a ?kind . '''+clause+''' }'''
    parents={uri.rsplit('/',1)[0].lstrip('/') for uri in uris}
    return sorted(str(row.path) for row in graph.query(query) if str(row.path).lstrip('/') in parents)
