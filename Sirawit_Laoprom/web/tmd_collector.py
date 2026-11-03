"""One hourly API fetch, written directly to both MongoDB destinations."""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')
if os.getenv('WEATHER_ENV_FILE'):
    load_dotenv(os.environ['WEATHER_ENV_FILE'])
STATE = BASE / 'collector_state'
KEYS = ('province', 'amphoe', 'tambon', 'forecast_time')

def parse_forecasts(payload, area, now=None):
    if not isinstance(payload, dict):
        raise ValueError('API response must be an object')
    entries = payload.get('WeatherForecasts', payload.get('WeatherForcasts'))
    if not isinstance(entries, list):
        raise ValueError('API forecast list missing')
    now = now or datetime.now(timezone.utc)
    docs = {}
    for item in entries:
        for forecast in item.get('forecasts', []):
            moment = datetime.fromisoformat(forecast['time'].replace('Z', '+00:00'))
            if moment.tzinfo is None:
                raise ValueError('API time requires timezone')
            timestamp = moment.astimezone(timezone(timedelta(hours=7))).isoformat()
            data = forecast.get('data')
            if not isinstance(data, dict) or not data:
                raise ValueError('API forecast data missing')
            doc = dict(area, forecast_time=timestamp, forecast_data=data,
                       api_location=item.get('location', {}), source='TMD',
                       created_at=now, updated_at=now, raw=forecast)
            docs[tuple(doc[k] for k in KEYS)] = doc
    if not docs:
        raise ValueError('API returned no forecasts')
    return list(docs.values())

def fetch_forecasts():
    url, key = os.getenv('TMD_API_URL'), os.getenv('TMD_API_KEY')
    if not url or not key:
        raise ValueError('TMD configuration missing')
    area = {'province': os.getenv('TMD_PROVINCE', 'สกลนคร'),
            'amphoe': os.getenv('TMD_AMPHOE', 'เมืองสกลนคร'),
            'tambon': os.getenv('TMD_TAMBON', 'เชียงเครือ')}
    params = dict(area, fields='tc,rh,slp,rain,ws10m,wd10m,cond', duration=1)
    response = requests.get(url, headers={'accept': 'application/json', 'authorization': f'Bearer {key}'}, params=params, timeout=(10, 45))
    response.raise_for_status()
    return parse_forecasts(response.json(), area)

def deliver(docs, collection):
    for doc in docs:
        values = dict(doc)
        created = values.pop('created_at')
        collection.update_one({k: doc[k] for k in KEYS},
                              {'$set': values, '$setOnInsert': {'created_at': created}}, upsert=True)
    return len(docs)


def safe_error(exc):
    # Never log exception text: network errors can include URIs or API tokens.
    result = {'error_type': type(exc).__name__}
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        result['http_status'] = exc.response.status_code
    return result

def run():
    STATE.mkdir(exist_ok=True)
    # OS-released lock prevents manual/scheduled overlap, even after a crash.
    import msvcrt
    with open(STATE / 'collector.lock', 'a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return {'status': 'already_running'}
        try:
            return run_locked()
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

def run_locked():
    status = {'started_at': datetime.now(timezone.utc).isoformat(), 'fetched': 0, 'destinations': {}}
    try:
        docs = fetch_forecasts()
        status['fetched'] = len(docs)
    except Exception as exc:
        docs = []
        status['fetch_error'] = safe_error(exc)
    destinations = {'local': os.getenv('LOCAL_MONGO_URI', 'mongodb://localhost:27017/'), 'atlas': os.getenv('ATLAS_MONGO_URI')}
    for name, uri in destinations.items():
        if not docs:
            status['destinations'][name] = {'error_type': 'FetchUnavailable'}
            continue
        if not uri:
            status['destinations'][name] = {'error_type': 'MissingConfiguration'}
            continue
        try:
            with MongoClient(uri, serverSelectionTimeoutMS=7000, connectTimeoutMS=7000, socketTimeoutMS=15000, tz_aware=True) as client:
                collection = client[os.getenv('DB_NAME', 'weather_db')][os.getenv('TMD_COLLECTION', 'tmd_weather')]
                collection.create_index([(k, 1) for k in KEYS], unique=True, name='tmd_location_forecast_unique')
                status['destinations'][name] = {'delivered': deliver(docs, collection)}
        except Exception as exc:
            status['destinations'][name] = safe_error(exc)
    status['finished_at'] = datetime.now(timezone.utc).isoformat()
    status['status'] = 'ok' if 'fetch_error' not in status and all('error_type' not in d for d in status['destinations'].values()) else 'needs_attention'
    temporary = STATE / 'status.tmp'
    temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(STATE / 'status.json')
    with open(STATE / 'runs.jsonl', 'a', encoding='utf-8') as log:
        log.write(json.dumps(status, ensure_ascii=False) + '\n')
    return status

if __name__ == '__main__':
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['status'] in ('ok', 'already_running') else 1)
