'use strict';
const $ = id => document.getElementById(id);
// Remember this browser's night-mode preference.
const themeKey = 'sponsor-panel-theme';
const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
let savedTheme = null;

try {
  savedTheme = localStorage.getItem(themeKey);
} catch {
  // The switch still works if browser storage is unavailable.
}

if (savedTheme !== 'dark' && savedTheme !== 'light') {
  savedTheme = null;
}

function applyTheme(dark) {
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  $('nightMode').checked = dark;
}

applyTheme(savedTheme ? savedTheme === 'dark' : systemTheme.matches);

$('nightMode').addEventListener('change', () => {
  const dark = $('nightMode').checked;
  savedTheme = dark ? 'dark' : 'light';
  applyTheme(dark);

  try {
    localStorage.setItem(themeKey, savedTheme);
  } catch {
    // Keep the selection for this page session.
  }
});

systemTheme.addEventListener('change', event => {
  if (savedTheme === null) {
    applyTheme(event.matches);
  }
});
let settingsRevision = '', csrf = '', state = null, candidate = null, renameId = null, dirty = false, busy = false;
let cursor = 0, logLines = [], logsPaused = false, noticeTimer, signedIn = false;
function notice(message, error=false) { $('notice').textContent=message; $('notice').className=error?'error':''; $('notice').hidden=false; clearTimeout(noticeTimer); noticeTimer=setTimeout(()=>$('notice').hidden=true,error?12000:5000); }
async function api(path, body) {
  const options={headers:{}};
  if(body!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-CSRF-Token':csrf};options.body=JSON.stringify(body);}
  const response=await fetch('/api/'+path,options);
  const data=await response.json();
  if(!response.ok){if(response.status===401 && path!=='login')showLogin();throw new Error(data.error||'Request failed.');}
  return data;
}
function showLogin(){signedIn=false;$('login').hidden=false;$('dashboard').hidden=true;}
function showDashboard(){signedIn=true;$('login').hidden=true;$('dashboard').hidden=false;}
function element(tag,text,className){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
function button(text,fn,cls='secondary'){const el=element('button',text,cls);el.type='button';el.addEventListener('click',fn);return el;}
async function action(fn){if(busy)return;busy=true;const buttons=[...document.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);try{await fn();}catch(e){notice(e.message,true);if(signedIn)try{await refresh();}catch{}}finally{busy=false;buttons.forEach(b=>b.disabled=false);}}
function renderSettings(){if(dirty)return;settingsRevision=state.revision;for(const k of ['mute_ads','skip_ads','skip_count_tracking'])$(k).checked=state.settings[k];$('minimum_skip_length').value=state.settings.minimum_skip_length;const box=$('categories');box.replaceChildren();for(const [key,label] of Object.entries(state.categories)){const l=element('label');const input=element('input');input.type='checkbox';input.value=key;input.checked=state.settings.skip_categories.includes(key);input.addEventListener('change',()=>dirty=true);l.append(input,document.createTextNode(label));box.append(l);}}
function render(){
  const running=state.service.running, paused=state.service.paused, enabled=state.devices.filter(d=>d.enabled).length;
  $('connection').textContent='Panel connected';$('connection').className='badge good';
  $('serviceStatus').textContent=running?'Running':paused?'Paused':enabled?'Needs attention':'Ready';
  $('serviceDetail').textContent=running?'Watching your enabled screens':paused?'Start when you are ready':enabled?'Review logs or restart the service':'Add or enable a device to begin';
  $('deviceCount').textContent=enabled+' / '+state.devices.length;$('totalCount').textContent=state.devices.length;
  $('adMode').textContent=state.settings.mute_ads&&state.settings.skip_ads?'Mute + skip':state.settings.mute_ads?'Mute':state.settings.skip_ads?'Skip':'Off';
  $('servicePause').textContent=paused?'Start service':'Pause service';
  $('networks').textContent='Allowed device networks: '+state.allowed_networks.join(', ');
  const list=$('deviceList');list.replaceChildren();
  if(!state.devices.length)list.append(element('div','No devices yet. Search the network or add a Chromecast by IP below.','empty'));
  for(const d of state.devices){
    const card=element('article',undefined,'device-card');const top=element('div',undefined,'device-top');top.append(element('span','▣','tv-icon'),element('span',d.enabled?'Enabled':'Paused','badge '+(d.enabled?'good':'')));
    card.append(top,element('h3',d.name),element('div',d.ip||'Imported from saved configuration','address'));
    const event=element('div',undefined,'device-event');event.append(element('span',d.event?d.event.message:'No activity reported this session.'));
    if(d.event)event.append(element('small','Last report: '+new Date(d.event.time*1000).toLocaleTimeString()));card.append(event);
    const actions=element('div',undefined,'device-actions');actions.append(button(d.enabled?'Pause device':'Enable device',()=>deviceAction(d,d.enabled?'disable':'enable')));
    const more=element('div');more.append(button('Rename',()=>{renameId=d.id;$('renameInput').value=d.name;$('renameDialog').showModal();},'quiet'),button('Remove',()=>{if(confirm('Remove '+d.name+' from this panel? A configuration backup will be kept.'))deviceAction(d,'remove');},'quiet danger'));actions.append(more);card.append(actions);list.append(card);
  }
  renderSettings();$('lastUpdated').textContent='Updated '+new Date().toLocaleTimeString();
}
async function refresh(){state=await api('state');render();}
function deviceAction(d,type){return action(async()=>{state=await api('device',{revision:state.revision,id:d.id,action:type});render();notice('Device updated.');});}
async function checkDevice(ip,name){candidate=await api('probe',{ip});$('pairIp').textContent=ip;$('deviceName').value=name||candidate.name;$('pairResult').hidden=false;$('pairResult').scrollIntoView({behavior:'smooth',block:'center'});}
function drawLogs(){const query=$('logFilter').value.toLowerCase();const view=$('logs');const nearBottom=view.scrollHeight-view.scrollTop-view.clientHeight<70;view.textContent=logLines.filter(l=>l.message.toLowerCase().includes(query)).map(l=>new Date(l.time*1000).toLocaleTimeString()+'  '+l.message).join('\n')||'No matching activity.';if(nearBottom)view.scrollTop=view.scrollHeight;}
async function fetchLogs(){if(logsPaused)return;const data=await api('logs?after='+cursor);if(data.cursor<cursor){cursor=0;logLines=[];return;}cursor=data.cursor;logLines.push(...data.logs);logLines=logLines.slice(-1500);drawLogs();}
$('loginForm').addEventListener('submit',e=>{e.preventDefault();action(async()=>{const data=await api('login',{password:$('password').value});csrf=data.csrf;$('password').value='';showDashboard();await refresh();await fetchLogs();});});
$('logout').addEventListener('click',()=>action(async()=>{await api('logout',{});csrf='';logLines=[];cursor=0;showLogin();}));
$('refresh').addEventListener('click',()=>action(async()=>{dirty=false;await refresh();}));
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-view]').forEach(n=>n.classList.toggle('active',n===b));document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!=='view-'+b.dataset.view);$('pageTitle').textContent={devices:'Your devices',settings:'Playback settings',logs:'Activity & logs'}[b.dataset.view];$('pageDescription').textContent={devices:'Choose where to mute ads and skip sponsored segments.',settings:'Make the most of your viewing time.',logs:'See what your service is doing, as it happens.'}[b.dataset.view];}));
$('settingsForm').addEventListener('input',()=>dirty=true);
$('settingsForm').addEventListener('submit',e=>{e.preventDefault();action(async()=>{const settings={};for(const k of ['mute_ads','skip_ads','skip_count_tracking'])settings[k]=$(k).checked;settings.minimum_skip_length=Number($('minimum_skip_length').value);settings.skip_categories=[...$('categories').querySelectorAll('input:checked')].map(x=>x.value);state=await api('settings',{revision:settingsRevision,settings});dirty=false;render();notice('Settings saved. Previous configuration backed up.');});});
for(const [id,getAction] of [['servicePause',()=>state.service.paused?'start':'pause'],['restart',()=>'restart']])$(id).addEventListener('click',()=>action(async()=>{state=await api('service',{revision:state.revision,action:getAction()});render();notice('Service updated.');}));
$('scan').addEventListener('click',()=>action(async()=>{const area=$('scanResults');area.textContent='Searching for Google Cast devices…';try{const data=await api('scan',{});area.replaceChildren();if(!data.devices.length)area.append(element('p','No Cast devices found on this network. Use the IP field to reach a device on another VLAN.'));for(const d of data.devices){const row=element('div',undefined,'scan-row');const info=element('div');info.append(element('strong',d.name),element('small',d.ip+' · '+d.model));row.append(info,button('Connect YouTube',()=>action(()=>checkDevice(d.ip,d.name))));area.append(row);}}catch(e){area.textContent='Search did not complete.';throw e;}}));
$('probeForm').addEventListener('submit',e=>{e.preventDefault();action(()=>checkDevice($('deviceIp').value.trim()));});
$('addForm').addEventListener('submit',e=>{e.preventDefault();action(async()=>{state=await api('add',{revision:state.revision,candidate:candidate.candidate,name:$('deviceName').value});candidate=null;$('pairResult').hidden=true;render();notice('Device added and enabled.');});});
$('cancelAdd').addEventListener('click',()=>{candidate=null;$('pairResult').hidden=true;});
$('cancelRename').addEventListener('click',()=>$('renameDialog').close());
$('renameForm').addEventListener('submit',e=>{e.preventDefault();action(async()=>{state=await api('device',{revision:state.revision,id:renameId,action:'rename',name:$('renameInput').value});$('renameDialog').close();render();notice('Device renamed.');});});
$('pauseLogs').addEventListener('click',()=>{logsPaused=!logsPaused;$('pauseLogs').textContent=logsPaused?'Resume feed':'Pause feed';});
$('logFilter').addEventListener('input',drawLogs);
$('downloadLogs').addEventListener('click',()=>{const blob=new Blob([logLines.map(l=>new Date(l.time*1000).toISOString()+' '+l.message).join('\n')],{type:'text/plain'});const a=element('a');a.href=URL.createObjectURL(blob);a.download='isponsorblocktv-logs.txt';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);});
async function poll(){if(signedIn&&!busy){try{await refresh();await fetchLogs();}catch(e){$('connection').textContent='Connection interrupted';$('connection').className='badge warn';}}setTimeout(poll,4000);}
(async()=>{try{csrf=(await api('session')).csrf;showDashboard();await refresh();await fetchLogs();}catch{showLogin();}poll();})();
