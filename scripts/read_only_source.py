"""Local test helper: authenticated GET requests to existing HA states only.

No service calls, state writes, templates, redirects or proxy forwarding.
Credentials belong in ignored local output, never in distributable examples.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

ENTITY = re.compile(r"^sensor\.[a-z0-9_]+$")
REMOTE_STAMP = 'grid_peak_source_reported_at'


class ReadError(Exception):
    """Only a fixed, non-sensitive error code may cross the setup boundary."""


def base_url(value):
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError
        if parsed.path not in ('','/') and not parsed.path.startswith('/lovelace'):
            raise ValueError
        _ = parsed.port
        return f'{parsed.scheme}://{parsed.netloc}'.rstrip('/')
    except (ValueError,AttributeError):
        raise ReadError('invalid_url') from None


@dataclass(frozen=True)
class SourceConfig:
    url: str
    token: str = field(repr=False)
    power_entity: str
    energy_entity: str
    import_sign: int = 1
    target_kw: float = 8.0
    max_age: int = 120
    energy_resolution_kwh: float = 0.0

    @classmethod
    def parse(cls, data):
        try:
            result = cls(url=base_url(data['url']), token=data['token'],
                power_entity=data['power_entity'],energy_entity=data['energy_entity'],
                import_sign=int(data.get('import_sign',1)),target_kw=float(data.get('target_kw',8)),max_age=int(data.get('max_age',120)),energy_resolution_kwh=float(data.get('energy_resolution_kwh',0)))
            if not isinstance(result.token,str) or not result.token.strip() or len(result.token)>8192 or any(c in result.token for c in '\r\n'):
                raise ValueError
            if not all(ENTITY.fullmatch(e) for e in (result.power_entity,result.energy_entity)) or result.power_entity==result.energy_entity:
                raise ValueError
            if result.import_sign not in (-1,1) or not .1<=result.target_kw<=1000 or not 30<=result.max_age<=900:
                raise ValueError
            if not math.isfinite(result.energy_resolution_kwh) or not 0<=result.energy_resolution_kwh<=1:
                raise ValueError
            return result
        except (KeyError,TypeError,ValueError):
            raise ReadError('invalid_config') from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StateReader:
    def __init__(self,url,token,entities=()):
        self.url=base_url(url)
        if not isinstance(token,str) or not token.strip() or any(c in token for c in '\r\n'):
            raise ReadError('invalid_token')
        if any(not ENTITY.fullmatch(e) for e in entities):
            raise ReadError('invalid_entity')
        self._token=token
        self._allowed={'/api/states/'+e for e in entities}
        self._opener=build_opener(ProxyHandler({}),NoRedirect())

    def _get(self,path,*,discovery=False):
        if not (path in self._allowed or discovery and path=='/api/states'):
            raise ReadError('endpoint_blocked')
        request=Request(self.url+path,headers={'Authorization':'Bearer '+self._token,'Accept':'application/json'},method='GET')
        try:
            with self._opener.open(request,timeout=8) as response:
                limit=8*1024*1024 if discovery else 1024*1024
                data=response.read(limit+1)
                if len(data)>limit:raise ReadError('response_too_large')
                return json.loads(data)
        except HTTPError as error:
            code='auth_failed' if error.code in (401,403) else 'entity_missing' if error.code==404 else 'redirect_blocked' if 300<=error.code<400 else 'http_error'
            error.close()
            raise ReadError(code) from None
        except (URLError,TimeoutError,OSError):
            raise ReadError('connection_failed') from None
        except (ValueError,UnicodeError):
            raise ReadError('invalid_response') from None

    def discover(self):
        states=self._get('/api/states',discovery=True)
        if not isinstance(states,list):raise ReadError('invalid_response')
        result=[]
        for state in states:
            if not isinstance(state,dict):continue
            entity=state.get('entity_id','')
            attrs=state.get('attributes',{})
            if not isinstance(entity,str) or not ENTITY.fullmatch(entity) or not isinstance(attrs,dict):continue
            unit=attrs.get('unit_of_measurement')
            kind='power' if unit in ('W','kW') else 'energy' if unit in ('Wh','kWh','MWh') and attrs.get('state_class') in ('total','total_increasing') else None
            if kind:
                result.append({'entity_id':entity,'name':str(attrs.get('friendly_name',entity)),
                    'state':str(state.get('state','unknown')),'unit':unit,'kind':kind})
        return result

    def pair(self,config):
        # This reader is pinned to the configured two entities.
        return (normalize_state(self._get('/api/states/'+config.power_entity),config.power_entity,'power'),
                normalize_state(self._get('/api/states/'+config.energy_entity),config.energy_entity,'energy'))


def normalize_state(state,entity,kind):
    if not isinstance(state,dict) or state.get('entity_id')!=entity or not isinstance(state.get('attributes'),dict):
        raise ReadError('invalid_response')
    attrs=state['attributes']
    stamp=state.get('last_reported',state.get('last_updated'))
    try:
        parsed=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if parsed.tzinfo is None:raise ValueError
    except (TypeError,ValueError,AttributeError):
        raise ReadError('invalid_timestamp') from None
    units=('W','kW') if kind=='power' else ('Wh','kWh','MWh')
    value=state.get('state')
    output={k:attrs[k] for k in ('unit_of_measurement','state_class','device_class') if k in attrs}
    output[REMOTE_STAMP]=parsed.astimezone(timezone.utc).isoformat()
    output['friendly_name']='Netzleistung · lesende Kopie' if kind=='power' else 'Netzimport · lesende Kopie'
    if value in ('unavailable','unknown'):
        return {'state':'unavailable','attributes':output}
    try:
        numeric=float(value)
        if isinstance(value,bool) or not math.isfinite(numeric) or attrs.get('unit_of_measurement') not in units:
            raise ValueError
        if kind=='energy' and (numeric<0 or attrs.get('state_class') not in ('total','total_increasing')):
            raise ValueError
    except (TypeError,ValueError):
        raise ReadError('invalid_sensor') from None
    return {'state':str(value),'attributes':output}
