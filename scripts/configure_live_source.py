"""Loopback-only setup page. Secrets are entered locally, never via chat/CLI args."""
import argparse
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import tempfile

from read_only_source import StateReader, SourceConfig, ReadError, base_url

ROOT=Path(__file__).resolve().parents[1]
DESTINATION=ROOT/'output/live-source.json'
ERRORS={
    'invalid_url':'Bitte eine HA-Basisadresse ohne Zugangsdaten oder URL-Parameter eingeben.',
    'invalid_token':'Bitte den vorhandenen Token eingeben.',
    'auth_failed':'Die Anmeldung wurde abgelehnt. Token und Quelladresse prüfen.',
    'connection_failed':'Die produktive HA-Instanz ist nicht erreichbar.',
    'redirect_blocked':'Die Adresse leitet weiter. Bitte die direkte HA-Adresse verwenden.',
    'invalid_config':'Bitte beide unterschiedlichen Sensoren und gültige Einstellungen auswählen.',
    'invalid_sensor':'Ein ausgewählter Sensor hat keine passende Zahl, Einheit oder Zustandsklasse.',
    'entity_missing':'Ein ausgewählter Sensor wurde nicht gefunden.',
    'sensor_unavailable':'Beide Quellen müssen für die Einrichtung einen numerischen Wert liefern.',
}
PAGE=r'''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Echte Messdaten · lokale Einrichtung</title>
<style>body{font:16px/1.5 system-ui;background:#eee8dc;color:#182729;margin:0}main{max-width:760px;margin:32px auto;padding:24px}h1{font-size:30px}label{display:block;margin:16px 0}input,select,button{font:inherit;padding:10px;border-radius:7px;border:1px solid #78918a;box-sizing:border-box}input,select{display:block;width:100%;background:#fffaf0;color:#182729}button{background:#182729;color:#f3eee3;cursor:pointer;margin:8px 0}small{display:block;color:#526361}#status{padding:14px;border-radius:8px;background:#fffaf0;white-space:pre-wrap}a{color:#75412d}</style>
<main><h1>Echte Messdaten übernehmen</h1><p>Diese Seite läuft nur auf dem Mac mini. Der Abruf verwendet ausschließlich <strong>GET</strong> auf der produktiven HA-Instanz. Kopierte Sensoren und unser Monitor entstehen ausschließlich im Test-HA.</p>
<form id="setup"><label>Produktive HA-Adresse<input id="url" type="url" required autocomplete="off"></label><label>Vorhandener Zugriffstoken<input id="token" type="password" required autocomplete="off" spellcheck="false"></label><small>Der Token wird weder im Chat noch in einem Download gespeichert. Nach dem Speichern liegt er nur in einer privaten lokalen Datei.</small><button type="button" id="inspect">Passende Sensoren suchen</button>
<div id="sensors" hidden><label>Sensoren filtern<input id="sensor-search" type="search" placeholder="Name oder Entity-ID, z. B. Stromzähler" autocomplete="off" aria-describedby="sensor-count"></label><small id="sensor-count" role="status" aria-live="polite"></small><label>Gesamte Netzleistung<select id="power" required></select></label><label>Fortlaufende Bezugsenergie aus dem Netz<select id="energy" required></select></label><small>Für Energie den kumulierten Netzimport wählen, nicht PV-Ertrag, Haushaltsverbrauch oder einen Tageszähler.</small><label>Bezugsrichtung<select id="sign"><option value="1">Netzbezug ist positiv</option><option value="-1">Netzbezug ist negativ</option></select></label><label>Persönliches Ziel in kW<input id="target" type="number" min="0.1" max="1000" step="0.1" value="8" required></label><label>Maximales Meldealter in Sekunden<input id="age" type="number" min="30" max="900" step="1" value="120" required></label><label>Zählerauflösung in kWh<input id="resolution" type="number" min="0" max="1" step="0.001" value="0" required></label><small>0 = strenge Meldefrist. Für nur bei Änderung meldende Zähler die bekannte Auflösung angeben, z. B. 0,01 kWh für 10 Wh.</small><button type="submit">Lesende Übernahme starten</button></div></form>
<p id="status" role="status">Token eingeben und Sensoren suchen. Es wird nichts auf der produktiven Instanz eingerichtet.</p>
<p><a href="http://127.0.0.1:8124/lovelace/echte-messdaten" target="_blank" rel="noopener">Echte Messdaten im angemeldeten Test-HA öffnen</a></p><small>Falls du die HA-Ersteinrichtung noch nicht abgeschlossen hast, dort zuerst einen eigenen Testbenutzer anlegen.</small></main>
<script>
const csrf=__NONCE__,initialUrl=__SOURCE__;
document.querySelector('#url').value=initialUrl;
const status=document.querySelector('#status');
let sensors=[];
const chosen={power:'',energy:''};
const folded=value=>String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('de');
function renderSensors(){
 const terms=folded(document.querySelector('#sensor-search').value).trim().split(/\s+/).filter(Boolean);
 const counts={};
 for(const kind of ['power','energy']){
  const select=document.querySelector('#'+kind);
  const available=sensors.filter(item=>item.kind===kind);
  const matches=available.filter(item=>terms.every(term=>folded(item.name+' '+item.entity_id).includes(term)));
  const selected=available.find(item=>item.entity_id===chosen[kind]);
  const options=[...matches];
  if(selected&&!matches.includes(selected))options.unshift(selected);
  counts[kind]=matches.length;
  select.replaceChildren();
  const empty=document.createElement('option');empty.value='';empty.textContent=matches.length?'Bitte wählen':'Keine Treffer';select.append(empty);
  for(const item of options){const option=document.createElement('option');option.value=item.entity_id;option.textContent=(item===selected&&!matches.includes(item)?'Ausgewählt · ':'')+item.name+' · '+item.state+' '+item.unit+' · '+item.entity_id;select.append(option);}
  select.value=selected?selected.entity_id:'';
 }
 document.querySelector('#sensor-count').textContent='Treffer: Leistung '+counts.power+' · Energie '+counts.energy+'. Bereits gewählte Sensoren bleiben erhalten.';
}
for(const kind of ['power','energy'])document.querySelector('#'+kind).addEventListener('change',event=>{chosen[kind]=event.target.value;});
document.querySelector('#sensor-search').addEventListener('input',renderSensors);
document.querySelector('#sensor-search').addEventListener('keydown',event=>{if(event.key==='Enter')event.preventDefault();});
async function send(path,extra={}){
 const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Setup-Nonce':csrf},body:JSON.stringify({url:document.querySelector('#url').value,token:document.querySelector('#token').value,...extra})});
 const result=await response.json();if(!response.ok)throw new Error(result.error||'Abruf fehlgeschlagen.');return result;
}
document.querySelector('#inspect').onclick=async()=>{
 status.textContent='Sensoren werden lesend abgerufen …';
 try{const data=await send('/inspect');sensors=data.sensors;renderSensors();
 document.querySelector('#sensors').hidden=false;status.textContent='Sensoren gefunden. Bitte die zwei Quellen und die Bezugsrichtung auswählen.';}catch(error){status.textContent=error.message;}
};
document.querySelector('#setup').onsubmit=async event=>{
 event.preventDefault();if(!event.target.reportValidity())return;status.textContent='Auswahl wird lesend geprüft …';
 try{await send('/save',{power_entity:document.querySelector('#power').value,energy_entity:document.querySelector('#energy').value,import_sign:Number(document.querySelector('#sign').value),target_kw:Number(document.querySelector('#target').value),max_age:Number(document.querySelector('#age').value),energy_resolution_kwh:Number(document.querySelector('#resolution').value)});
 document.querySelector('#token').value='';status.textContent='Lokal gespeichert. Die Testinstanz übernimmt die Quellen in wenigen Sekunden. Öffne dort die Ansicht „Echte Messdaten“. Das erste vollständige Viertel muss erst erfasst werden.';}catch(error){status.textContent=error.message;}
};
</script></html>'''


def save_private(config,destination=DESTINATION):
    destination.parent.mkdir(exist_ok=True,parents=True)
    fd,temporary=tempfile.mkstemp(dir=destination.parent,prefix='.live-source-')
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as output:
            json.dump({'version':1,**asdict(config)},output)
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-url',default='')
    args=parser.parse_args()
    source=base_url(args.source_url) if args.source_url else ''
    nonce=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def send(self,status,body,content_type='application/json'):
            payload=body.encode() if isinstance(body,str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type+'; charset=utf-8')
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Referrer-Policy','no-referrer')
            self.end_headers()
            self.wfile.write(payload)

        def allowed(self):
            return self.headers.get('Host') in ('127.0.0.1:8125','localhost:8125')

        def do_GET(self):
            if not self.allowed():return self.send(403,{'error':'Nur lokaler Zugriff erlaubt.'})
            if self.path!='/':return self.send(404,{'error':'Nicht gefunden.'})
            self.send(200,PAGE.replace('__NONCE__',json.dumps(nonce)).replace('__SOURCE__',json.dumps(source)),'text/html')

        def do_POST(self):
            origin=self.headers.get('Origin')
            if not self.allowed() or self.headers.get('X-Setup-Nonce')!=nonce or origin not in (None,'http://127.0.0.1:8125','http://localhost:8125'):
                return self.send(403,{'error':'Bitte die lokale Einrichtungsseite verwenden.'})
            if self.path not in ('/inspect','/save'):return self.send(404,{'error':'Nicht gefunden.'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=32768:raise ReadError('invalid_config')
                data=json.loads(self.rfile.read(length))
                if self.path=='/inspect':
                    result={'sensors':StateReader(data['url'],data['token']).discover()}
                else:
                    config=SourceConfig.parse(data)
                    pair=StateReader(config.url,config.token,(config.power_entity,config.energy_entity)).pair(config)
                    if any(s['state']=='unavailable' for s in pair):raise ReadError('sensor_unavailable')
                    save_private(config)
                    result={'saved':True}
                self.send(200,result)
            except ReadError as error:
                self.send(400,{'error':ERRORS.get(str(error),'Abruf fehlgeschlagen. Adresse, Token und Sensoren prüfen.')})
            except (ValueError,TypeError,KeyError):
                self.send(400,{'error':'Eingaben sind unvollständig oder ungültig.'})
            except Exception:
                self.send(500,{'error':'Lokale Einrichtung fehlgeschlagen. Es wurden keine Befehle an die produktive Instanz gesendet.'})
    server=ThreadingHTTPServer(('127.0.0.1',8125),Handler)
    print('Local source setup ready: http://127.0.0.1:8125/',flush=True)
    server.serve_forever()


if __name__=='__main__':main()
