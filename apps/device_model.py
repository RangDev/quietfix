"""Shared machine/sensor schema. Sensors are readings, not oneM2M AEs."""
import math
import re

LEGACY = {
    'temperature_c': ('temperature', '온도', '°C'),
    'vibration_rms_mm_s': ('vibration_rms', '진동 RMS', 'mm/s'),
    'current_a': ('current', '전류', 'A'),
}
RULES = {'temperature': ('°C', 75), 'vibration_rms': ('mm/s', 7)}

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise ValueError('IDs must be 1–64 ASCII letters/digits, hyphens or underscores')
    return value

def normalize(row):
    """One row is a complete current sensor snapshot for one machine."""
    row = dict(row)
    identifier(row.get('machine_id'))
    sensors = row.get('sensors')
    if sensors is None:
        sensors = [{'sensor_id': key, 'type': kind, 'label': label, 'unit': unit,
                    'value': row[key]} for key, (kind, label, unit) in LEGACY.items() if key in row]
    if not isinstance(sensors, list) or not sensors:
        raise ValueError('At least one sensor is required')
    normalized, seen = [], set()
    for sensor in sensors:
        if not isinstance(sensor, dict):
            raise ValueError('Each sensor must be an object')
        sid = identifier(sensor.get('sensor_id'))
        if sid in seen:
            raise ValueError(f'Duplicate sensor_id: {sid}')
        seen.add(sid)
        value = sensor.get('value')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{sid}: value must be a finite number')
        result = {'sensor_id': sid, 'value': value}
        for field, default in [('type', 'other'), ('label', sid), ('unit', '')]:
            text = sensor.get(field, default)
            if not isinstance(text, str) or len(text) > 120:
                raise ValueError(f'{sid}: {field} must be a string of at most 120 characters')
            result[field] = text
        normalized.append(result)
    row['sensors'] = normalized
    name = row.get('machine_name', row['machine_id'])
    if not isinstance(name, str) or len(name) > 120:
        raise ValueError('machine_name must be a string of at most 120 characters')
    row['machine_name'] = name
    return row

def sensor_status(sensor):
    rule = RULES.get(sensor['type'])
    if rule is None or sensor['unit'] != rule[0]:
        return 'unassessed'
    return 'abnormal' if sensor['value'] >= rule[1] else 'normal'

def machine_status(sensors):
    statuses = {sensor_status(s) for s in sensors}
    return 'abnormal' if 'abnormal' in statuses else 'normal' if 'normal' in statuses else 'unassessed'
