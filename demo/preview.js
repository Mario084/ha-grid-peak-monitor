import '/grid_peak_monitor_static/grid-peak-card.js?v=0.1.0-alpha.5';
const mount = document.querySelector('#dashboard');
const status = document.querySelector('#connection');
const failure = document.querySelector('#failure');
const card = document.createElement('grid-peak-card');
let target = null;
card.setConfig({entity:'sensor.demo_forecast',title:'Netzspitzen im Blick',devices:['sensor.demo_heating','sensor.demo_kitchen','sensor.demo_base']});
const callWS = async request => {
  if(request.type !== 'grid_peak_monitor/history') throw new Error('Demo supports local history only');
  const response = await fetch('/demo-data?'+new URLSearchParams({date:request.date,month:request.month}),{cache:'no-store'});
  if(!response.ok) throw new Error('History unavailable');
  return response.json();
};
async function refresh(){
  try{
    const response=await fetch('/demo-data',{cache:'no-store'});
    if(!response.ok)throw new Error('Demo unavailable');
    const data=await response.json();
    const snapshot={...data.snapshot};
    if(target!==null){
      snapshot.target_kw=target;
      if(snapshot.used_kwh!==null&&snapshot.remaining_seconds>0){
        snapshot.allowed_power_kw=Math.max(0,(target/4-snapshot.used_kwh)*3600/snapshot.remaining_seconds);
        snapshot.additional_power_kw=snapshot.allowed_power_kw-snapshot.power_kw;
      }
      snapshot.headroom_kw=snapshot.forecast_kw===null?null:target-snapshot.forecast_kw;
      snapshot.status=snapshot.forecast_kw===null?'no_data':snapshot.minimum_kw>target?'exceeded':snapshot.minimum_kw>=target?'reached':snapshot.forecast_kw>target?'risk':snapshot.forecast_kw>=.9*target?'near':'below';
    }
    card.hass={config:{time_zone:data.zone},callWS,states:{
      'sensor.demo_forecast':{state:String(snapshot.forecast_kw??'unknown'),attributes:{grid_peak_monitor:true,monitor_id:data.monitor_id,metric:'forecast_kw',snapshot}},
      ...data.devices,
    }};
    if(!card.isConnected)mount.append(card);
    if(target===null)document.querySelector('#target').value=String(snapshot.target_kw);
    status.textContent='Verbunden · Beispieldaten aktualisiert um '+new Date(data.now*1000).toLocaleTimeString('de-AT');
    failure.hidden=true;
  }catch(error){status.textContent='Verbindung unterbrochen – erneuter Versuch folgt.';failure.hidden=false;failure.textContent='Die lokale Vorschau ist gerade nicht erreichbar. Die zuletzt geladenen Werte werden nicht weiter aktualisiert.';}
}
document.querySelector('#apply').onclick=()=>{
  const input=document.querySelector('#target');
  if(!input.reportValidity())return;
  target=Number(input.value);refresh();
};
await refresh();
setInterval(refresh,5000);
