import os
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from flask import Flask, render_template, request, g
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
if os.getenv('WEATHER_ENV_FILE'):
    load_dotenv(os.environ['WEATHER_ENV_FILE'])
app = Flask(__name__)
THAI = timezone(timedelta(hours=7))
client = None
sensor_client = None
local_sensor_client = None
FIELDS = [('temperature', 'อุณหภูมิ', '°C', 'tc'), ('humidity', 'ความชื้น', '%', 'rh'), ('pressure', 'ความกดอากาศ', 'hPa', 'slp'), ('wind_speed', 'ความเร็วลม', 'm/s', 'ws10m')]
SENSOR_FIELDS = FIELDS + [('co2', 'CO₂', 'ppm', ''), ('light', 'ความเข้มแสง', 'lux', '')]

def parse_time(value):
    if isinstance(value, dict):
        value = value.get('$date')
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(THAI)

def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None

def normalize(doc, sensor=False):
    raw_time = doc.get('timestamp' if sensor else 'forecast_time')
    if sensor and isinstance(raw_time, str):
        try:
            parsed = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
            raw_time = parsed.replace(tzinfo=THAI) if parsed.tzinfo is None else parsed
        except ValueError:
            pass
    moment = parse_time(raw_time)
    if not moment:
        return None
    data = (doc if sensor else doc.get('forecast_data')) or {}
    row = {'time': moment, 'timestamp': moment.strftime('%d/%m/%Y %H:%M'), 'iso': moment.isoformat()}
    for key, _, _, tmd_key in SENSOR_FIELDS:
        row[key] = number(data.get(key if sensor else tmd_key))
    if sensor:
        row['light'] = number(data.get('lux', data.get('light')))
        row['mq135'] = number(data.get('mq135'))
        row['station_id'] = str(doc.get('station_id', ''))
        row['observed_time'] = moment
        if number(data.get('ppm')) is not None:
            row['co2'] = number(data.get('ppm'))
        if row['co2'] is None and os.getenv('MQ135_IS_CO2_PPM', '').lower() == 'true':
            row['co2'] = row['mq135']
    for key in ('rain', 'wd10m', 'cond'):
        row[key] = number(data.get(key))
    row['saved'] = parse_time(doc.get('created_at'))
    return row

def date_query(field):
    """Filter in MongoDB before the 5,000-row cap so older days remain reachable."""
    date = request.args.get('date', '')
    if not date:
        return {}
    try:
        start = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=THAI)
    except ValueError:
        return {'_id': {'$exists': False}}
    converted = {'$convert': {'input': '$' + field, 'to': 'date', 'onError': None, 'onNull': None}}
    return {'$expr': {'$and': [{'$gte': [converted, start]}, {'$lt': [converted, start + timedelta(days=1)]}]}}

def read_sensor_docs(query):
    """Read one complete result set; always prefer Atlas on each request."""
    global sensor_client, local_sensor_client
    for source in ('atlas', 'local'):
        try:
            if source == 'atlas':
                uri = os.getenv('ATLAS_MONGO_URI')
                if not uri:
                    raise ValueError('Atlas configuration missing')
                if sensor_client is None:
                    sensor_client = MongoClient(uri, serverSelectionTimeoutMS=2000,
                        connectTimeoutMS=2000, socketTimeoutMS=2000, timeoutMS=2500, tz_aware=True)
                db = sensor_client[os.getenv('SENSOR_DB_NAME', os.getenv('DB_NAME', 'weather_db'))]
                collection = db[os.getenv('SENSOR_COLLECTION', 'test_sensor')]
            else:
                if local_sensor_client is None:
                    local_sensor_client = MongoClient('mongodb://localhost:27017/',
                        serverSelectionTimeoutMS=2000, connectTimeoutMS=2000,
                        socketTimeoutMS=2000, timeoutMS=2500, tz_aware=True)
                collection = local_sensor_client['weather_db']['test_sensor']
            # Materialize inside try: cursor iteration/getMore can also fail.
            docs = list(collection.find(query, {'_id': 0}).sort('timestamp', -1).limit(5000))
            g.sensor_source = source
            app.logger.info('sensor_source=%s', source)
            return docs
        except (PyMongoError, ValueError, OSError) as exc:
            app.logger.warning('sensor_source=%s unavailable (%s)', source, type(exc).__name__)
            if source == 'local':
                raise


def read_data():
    global client, sensor_client
    if hasattr(g, 'weather'):
        return g.weather
    sample = os.getenv('WEATHER_SAMPLE_FILE')
    status = 'ข้อมูลตัวอย่างจากไฟล์' if sample else 'เชื่อมต่อ MongoDB แล้ว'
    error = None
    sensor_docs, docs = [], []
    try:
        if sample:
            docs = json.loads(Path(sample).read_text(encoding='utf-8-sig'))
        else:
            uri = os.getenv('MONGO_URI')
            if not uri:
                raise ValueError('missing configuration')
            if client is None:
                client = MongoClient(uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, socketTimeoutMS=5000, tz_aware=True)
            db = client[os.getenv('DB_NAME', 'weather_db')]
            area = {'province': os.getenv('TMD_PROVINCE', 'สกลนคร'), 'amphoe': os.getenv('TMD_AMPHOE', 'เมืองสกลนคร'), 'tambon': os.getenv('TMD_TAMBON', 'เชียงเครือ')}
            area.update(date_query('forecast_time'))
            docs = list(db[os.getenv('TMD_COLLECTION', 'tmd_weather')].find(area, {'raw': 0}).sort('forecast_time', -1).limit(5000))
    except (PyMongoError, ValueError, OSError):
        status = 'ยังเชื่อมต่อข้อมูลไม่ได้'
        error = 'กรุณาตรวจสอบการตั้งค่า MongoDB และการเชื่อมต่อเซิร์ฟเวอร์ แล้วลองรีเฟรชอีกครั้ง'
    sensor_error = None
    if not sample:
        try:
            station = os.getenv('SENSOR_STATION_ID')
            query = {'station_id': station} if station else {}
            query.update(date_query('timestamp'))
            sensor_docs = read_sensor_docs(query)
        except (PyMongoError, ValueError, OSError):
            sensor_error = 'ยังเชื่อมต่อฐานข้อมูลเซนเซอร์ไม่ได้ กรุณาตรวจสอบการเชื่อมต่อแล้วลองใหม่'
    if request.path == '/' and not sample:
        error = sensor_error
        status = 'ยังเชื่อมต่อเซนเซอร์ไม่ได้' if sensor_error else 'เชื่อมต่อข้อมูลเซนเซอร์แล้ว'
    def rows(items, sensor=False):
        normalized = [normalize(d, sensor) for d in items]
        unique = {}
        for r in sorted((r for r in normalized if r), key=lambda r: r['saved'] or datetime.min.replace(tzinfo=THAI)):
            unique[r['iso']] = r
        return sorted(unique.values(), key=lambda r: r['time'])
    g.weather = {'tmd': rows(docs), 'sensor': rows(sensor_docs, True), 'status': status, 'error': error, 'sensor_error': sensor_error, 'sample': bool(sample)}
    return g.weather

@app.template_filter('value')
def value(v):
    return '—' if v is None else f'{v:,.2f}'.rstrip('0').rstrip('.')

@app.context_processor
def common():
    return dict(connection=read_data(), fields=FIELDS, sensor_fields=SENSOR_FIELDS, area=f"{os.getenv('TMD_TAMBON', 'เชียงเครือ')} · {os.getenv('TMD_PROVINCE', 'สกลนคร')}")

def selected(rows):
    date = request.args.get('date', '')
    if date:
        try:
            target = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return [], '', 'วันที่ไม่ถูกต้อง กรุณาเลือกวันที่ใหม่'
        rows = [r for r in rows if r['time'].date() == target]
    return rows[-168:], date, None

def chart(rows, keys):
    return {'labels': [r['timestamp'] for r in rows], 'series': {k: [r.get(k) for r in rows] for k in keys}}

def paginate(items):
    """Page the normalized table only; charts retain the full selected dataset."""
    total = len(items)
    pages = max(1, (total + 19) // 20)
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        page = 1
    page = max(1, min(page, pages))
    offset = (page - 1) * 20
    def link(number):
        args = [(key, value) for key, value in request.args.items(multi=True) if key != 'page']
        return request.path + '?' + urlencode(args + [('page', number)])
    numbers = sorted({1, pages, *range(max(1, page - 1), min(pages, page + 1) + 1)})
    links = []
    for number in numbers:
        if links and number > links[-1]['number'] + 1:
            links.append({'number': number - 1, 'url': None})
        links.append({'number': number, 'url': link(number)})
    return items[offset:offset + 20], dict(page=page, pages=pages, total=total,
        start=offset + 1 if total else 0, end=min(offset + 20, total), links=links,
        previous=link(page - 1) if page > 1 else None,
        next=link(page + 1) if page < pages else None)

def hourly_sensor(rows):
    """Use the latest observation in each Thai clock hour; never invent values."""
    hours = {}
    for row in sorted(rows, key=lambda r: r.get('observed_time', r['time'])):
        hour = row['time'].replace(minute=0, second=0, microsecond=0)
        hours[hour.isoformat()] = dict(row, time=hour, iso=hour.isoformat(),
                                      timestamp=hour.strftime('%d/%m/%Y %H:%M'))
    return list(hours.values())

@app.route('/')
def index():
    data = read_data()
    latest = max(data['sensor'], key=lambda r: r.get('observed_time', r['time']), default=None)
    stale = bool(latest and latest.get('observed_time', latest['time']) < datetime.now(THAI) - timedelta(minutes=90))
    return render_template('index.html', latest=latest, stale=stale)

@app.route('/tmd')
@app.route('/history')
def records():
    sensor = request.path == '/history'
    rows, date, error = selected(read_data()['sensor' if sensor else 'tmd'])
    table_rows, pagination = paginate(list(reversed(rows)))
    return render_template('records.html', records=table_rows, pagination=pagination, selected_date=date, filter_error=error, is_sensor=sensor, plot=chart(rows, [f[0] for f in SENSOR_FIELDS]))

@app.route('/compare')
def compare():
    data = read_data()
    sensor, date, error = selected(hourly_sensor(data['sensor']))
    forecasts = {r['time'].replace(minute=0, second=0, microsecond=0).isoformat(): r for r in data['tmd']}
    pairs = [(r, forecasts[r['iso']]) for r in sensor if r['iso'] in forecasts]
    plot = {'labels': [s['timestamp'] for s, _ in pairs], 'series': {}}
    for key, _, _, _ in FIELDS:
        plot['series'][key] = [s[key] for s, _ in pairs]
        plot['series']['tmd_' + key] = [t[key] for _, t in pairs]
    table_indices, pagination = paginate(list(range(len(pairs) - 1, -1, -1)))
    return render_template('compare.html', plot=plot, table_indices=table_indices, pagination=pagination, selected_date=date, filter_error=error, count=len(pairs))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')), debug=False)
