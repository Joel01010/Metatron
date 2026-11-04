(() => {
'use strict';

const state = { status:null, settings:null, eventsSeq:0, liveSeq:0, view:'command', polling:false };
const titles = {
  command:['Command Center','Local-first orchestration under a strict memory budget'],
  tasks:['Kanban','Tasks shared by you and your agents'],
  agents:['Agents','E.O.P., Ezra, Codex, Claude Code and OpenCode'],
  hardware:['Hardware','Cross-vendor acceleration with explicit NPU → GPU → CPU fallback'],
  voice:['Voice & Presence','Important-system TTS and reactive procedural presence'],
  metrics:['Metrics','Runtime memory, telemetry and model residency'],
  settings:['Settings','Appearance, presence, voice, hardware, memory and privacy'],
};
const statuses=['backlog','ready','running','review','blocked','done'];
const $=q=>document.querySelector(q); const $$=q=>[...document.querySelectorAll(q)];

async function invoke(cmd, params={}) {
  try {
    if (window.__TAURI__?.core?.invoke) {
      return await window.__TAURI__.core.invoke('backend_command',{cmd,params});
    }
    throw new Error('Metatron desktop bridge is unavailable. Run this UI through the Tauri app.');
  } catch (e) {
    const msg=String(e?.message||e);
    $('#backendState')?.classList.remove('online'); $('#backendState')?.classList.add('offline');
    throw new Error(msg);
  }
}
async function nativeWindow(action,value=null){
  if(window.__TAURI__?.core?.invoke)return window.__TAURI__.core.invoke('window_command',{action,value});
}
function toast(message){const t=$('#toast');t.textContent=message;t.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove('show'),2800)}
function esc(x){return String(x??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function fmtMiB(n){if(n==null)return '—'; n=Number(n);return n>1024?`${(n/1024).toFixed(2)} GiB`:`${n.toFixed(0)} MiB`}
function fmtPct(n){return Number.isFinite(Number(n))?`${Number(n).toFixed(0)}%`:'—'}
function timeText(ts){try{return new Date(Number(ts)*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}catch{return '—'}}

function setView(name){
  state.view=name; $$('.view').forEach(x=>x.classList.toggle('active',x.id===`view-${name}`));
  $$('#nav button').forEach(x=>x.classList.toggle('active',x.dataset.view===name));
  const [a,b]=titles[name]||titles.command; $('#viewTitle').textContent=a;$('#viewSubtitle').textContent=b;
  if(name==='tasks') renderTasks(); if(name==='agents') renderAgents(); if(name==='hardware') renderHardware(); if(name==='metrics') renderMetrics(); if(name==='settings') renderSettings();
  invoke('presence.dashboard',{open:true}).catch(()=>{});
}

async function refreshStatus(){
  const s=await invoke('status'); state.status=s; state.settings=s.settings;
  $('#backendState').classList.add('online');$('#backendState').classList.remove('offline');
  $('#backendState').textContent='● Backend'; $('#version').textContent=`v${s.version}`;
  renderCommand(); renderVoice();
  if(state.view==='agents')renderAgents(); if(state.view==='hardware')renderHardware(); if(state.view==='metrics')renderMetrics(); if(state.view==='settings')renderSettings();
}

function renderCommand(){
  const s=state.status;if(!s)return;
  $('#presenceState').textContent=s.presence?.state||'idle';
  $('#ttsToggle').textContent=`Voice: ${s.tts?.enabled?'On':'Off'}`;
  const mem=s.memory||{}; const used=Number(mem.platform_reserved_mib||0), cap=Number(mem.hard_limit_mib||1); const pct=Math.min(100,used/cap*100);
  $('#memoryBadge').textContent=s.memory_profile.toUpperCase(); $('#memoryFill').style.width=`${pct}%`;$('#memoryLabel').textContent=`${fmtMiB(used)} reserved / ${fmtMiB(cap)} hard ceiling`;
  const tm=s.telemetry||{}; const hw=s.hardware?.counts||{};
  $('#systemMetrics').innerHTML=[
    ['CPU',tm.cpu_percent!=null?fmtPct(tm.cpu_percent):'—'],['RAM',tm.rss_mib!=null?fmtMiB(tm.rss_mib):'—'],['NPU',`${hw.npu||0} detected`],['GPU',`${hw.gpu||0} detected`],
  ].map(([a,b])=>`<div class="metric"><small>${a}</small><b>${b}</b></div>`).join('');
  const agents=s.agents||[];
  $('#agentMiniList').innerHTML=agents.map(a=>`<div class="agent-row"><div class="agent-name"><i class="dot ${esc(a.state||'stopped')}"></i><span>${esc(a.label)}</span></div><small class="muted">${esc(a.state||'unknown')}</small></div>`).join('')||'<p class="muted">No agents registered.</p>';
  sendOrb({topic:'presence.state',payload:s.presence||{}}); if(s.presence?.quality)sendOrb(null,s.presence.quality);
}

async function pollEvents(){
  try{
    const ev=await invoke('events.tail',{after_seq:state.eventsSeq,limit:40});
    if(Array.isArray(ev)&&ev.length){state.eventsSeq=Math.max(...ev.map(x=>Number(x.seq||0)),state.eventsSeq);renderActivity(ev);ev.forEach(sendOrb)}
    const live=await invoke('events.live',{after_live_seq:state.liveSeq,limit:120});
    if(Array.isArray(live)&&live.length){state.liveSeq=Math.max(...live.map(x=>Number(x.live_seq||0)),state.liveSeq);live.forEach(sendOrb)}
  }catch{}
}
function renderActivity(events){
  const list=$('#activityList'); const rows=events.slice(-20).reverse().map(e=>`<div class="activity-row"><time>${timeText(e.ts)}</time><span><b>${esc(e.source)}</b> · ${esc(e.topic)}</span></div>`).join('');
  list.innerHTML=rows+list.innerHTML; while(list.children.length>30)list.lastElementChild.remove();
}
function sendOrb(ev,quality){const f=$('#orbFrame');try{f?.contentWindow?.postMessage(quality?{quality}:{metatronEvent:ev},'*')}catch{}}

async function renderTasks(){
  try{
    const tasks=await invoke('tasks.list',{limit:500}); const groups=Object.fromEntries(statuses.map(x=>[x,[]])); tasks.forEach(t=>(groups[t.status]||groups.backlog).push(t));
    $('#kanban').innerHTML=statuses.map(status=>`<div class="column"><h3>${status} · ${groups[status].length}</h3>${groups[status].map(taskCard).join('')}</div>`).join('');
    $$('.task-card button[data-move]').forEach(b=>b.onclick=async()=>{await invoke('tasks.move',{task_id:b.dataset.id,status:b.dataset.move,actor:'user'});renderTasks()});
  }catch(e){toast(e.message)}
}
function taskCard(t){
  const i=statuses.indexOf(t.status), prev=statuses[Math.max(0,i-1)], next=statuses[Math.min(statuses.length-1,i+1)];
  return `<article class="task-card"><strong>${esc(t.title)}</strong><small>${esc(t.project||'General')} · ${esc(t.agent_id||'Unassigned')}</small><div class="task-actions">${i>0?`<button data-id="${esc(t.id)}" data-move="${prev}">←</button>`:''}${i<statuses.length-1?`<button data-id="${esc(t.id)}" data-move="${next}">→</button>`:''}</div></article>`
}

async function renderAgents(){
  const agents=state.status?.agents||await invoke('agents.list');
  $('#agentGrid').innerHTML=agents.map(a=>`<article class="card"><div class="card-title"><strong>${esc(a.label)}</strong><span class="pill">${esc(a.state||'unknown')}</span></div><p>${esc(a.kind||'agent')} · ${esc(a.transport||'local')}</p><div class="row"><button class="primary agent-start" data-id="${esc(a.id)}">Start</button><button class="ghost agent-stop" data-id="${esc(a.id)}">Stop</button><button class="ghost agent-detect" data-id="${esc(a.id)}">Detect</button></div></article>`).join('');
  $$('.agent-start').forEach(b=>b.onclick=()=>agentAction('agent.start',b.dataset.id)); $$('.agent-stop').forEach(b=>b.onclick=()=>agentAction('agent.stop',b.dataset.id)); $$('.agent-detect').forEach(b=>b.onclick=()=>agentAction('agent.detect',b.dataset.id));
}
async function agentAction(cmd,id){try{const r=await invoke(cmd,{agent_id:id});toast(`${id}: ${r.state||r.available||'ok'}`);await refreshStatus()}catch(e){toast(e.message)}}

function renderHardware(){
  const h=state.status?.hardware;if(!h)return; const policy=h.policy||{};
  $('#devicePolicy').innerHTML=(policy.order||[]).map((x,i)=>`<span class="policy-chip">${i+1}. ${esc(x)}</span>`).join('');
  $('#hardwareCounts').innerHTML=[['Routable NPU',h.counts?.npu||0],['Routable GPU',h.counts?.gpu||0],['Detected NPU',h.counts?.detected_npu||0],['CPU fallback',policy.allow_cpu?'Enabled':'Restricted']].map(([a,b])=>`<div class="metric"><small>${a}</small><b>${b}</b></div>`).join('');
  const actual=Object.values(h.actual||{}); $('#actualDevices').innerHTML=actual.length?actual.map(a=>`<div class="device-row"><span>${esc(a.workload)}</span><b>${esc(a.kind)} · ${esc(a.device||a.provider)}</b></div>`).join(''):'<p class="muted">No runtime has reported actual placement yet. Metatron will never infer this from preference alone.</p>';
  $('#deviceGrid').innerHTML=(h.devices||[]).map(d=>`<article class="card"><div class="card-title"><strong>${esc(d.name)}</strong><span class="device-kind">${esc(d.kind)}</span></div><p>${esc(d.vendor)} · ${esc(d.provider)}</p><small class="muted">${esc(d.source)}${d.provider_device?' · '+esc(d.provider_device):''} · ${d.routable?'routable':'detected only'}</small></article>`).join('')||'<p class="muted">Only CPU fallback detected. Install/enable an NPU or GPU execution provider for acceleration.</p>';
}

function renderVoice(){
  const t=state.status?.tts;if(!t)return;
  $('#voiceControls').innerHTML=`
    ${settingToggle('TTS enabled','Speak important system events','voice-tts-enabled',!!t.enabled)}
    ${settingSelect('Mode','Premium uses Kokoro; light prefers Piper/SAPI','voice-mode',[['premium','Premium'],['light','Lightweight'],['off','Off']],t.mode)}
    ${settingInput('Voice','Kokoro voice ID','voice-id',t.voice||'am_fenrir')}
    ${settingInput('Speed','0.7–1.3','voice-speed',t.speed||0.96,'number','0.01')}
    ${settingInput('Speak threshold','0=silent … 4=urgent','voice-threshold',t.priority_threshold??3,'number','1')}`;
  bindVoiceControls();
  $('#ttsProviders').innerHTML=`<div class="resource-list">${(t.providers||[]).map(p=>`<div class="resource-row"><span>${esc(p.id)}</span><b>${p.available?'available':'not configured'}</b></div>`).join('')}</div>`;
}
function bindVoiceControls(){
  const save=async()=>{try{await invoke('settings.set',{section:'voice',values:{tts_enabled:$('#voice-tts-enabled').checked,tts_mode:$('#voice-mode').value,tts_voice:$('#voice-id').value,tts_speed:Number($('#voice-speed').value),tts_priority_threshold:Number($('#voice-threshold').value)}});await refreshStatus();toast('Voice settings saved')}catch(e){toast(e.message)}};
  ['voice-tts-enabled','voice-mode','voice-id','voice-speed','voice-threshold'].forEach(id=>{const e=$('#'+id);if(e)e.onchange=save});
}

function renderMetrics(){
  const s=state.status;if(!s)return; const tm=s.telemetry||{}, mem=s.memory||{};
  $('#metricCards').innerHTML=[['Backend RSS',fmtMiB(tm.rss_mib)],['Managed reserved',fmtMiB(mem.platform_reserved_mib)],['Hard limit',fmtMiB(mem.hard_limit_mib)],['Approvals',s.pending_approvals??0]].map(([a,b])=>`<article class="card"><small class="muted">${a}</small><div style="font-size:25px;margin-top:7px">${b}</div></article>`).join('');
  $('#budgetState').textContent=mem.within_budget?'within budget':'over budget';
  const usable=Number(mem.usable_mib||1); $('#memoryResources').innerHTML=(mem.resources||[]).sort((a,b)=>Number(b.charge_mib)-Number(a.charge_mib)).map(r=>`<div class="resource-row"><div class="resource-main"><b>${esc(r.name)}</b><small class="muted">${r.loaded?'loaded':'sleeping'} · ${esc(r.metadata?.role||r.metadata?.kind||'resource')}</small></div><div class="mini-bar"><i style="width:${Math.min(100,Number(r.charge_mib||0)/usable*100)}%"></i></div><span>${fmtMiB(Number(r.charge_mib||0))}</span></div>`).join('');
}

function renderSettings(){
  const all=state.settings;if(!all)return;
  const a=all.appearance,p=all.presence,h=all.hardware,m=all.memory,pr=all.privacy,ag=all.agents;
  $('#settingsGrid').innerHTML=`
  <section class="setting-card"><h2>Appearance</h2>${settingColor('Pale-red accent','Primary UI and spectral shell','set-accent',a.accent)}${settingColor('Golden core','Orb core and highlights','set-gold',a.gold)}${settingSelect('Density','Dashboard spacing','set-density',[['comfortable','Comfortable'],['compact','Compact']],a.density)}${settingToggle('Reduce motion','Lower animation activity','set-motion',a.reduce_motion)}</section>
  <section class="setting-card"><h2>Presence</h2>${settingSelect('Orb quality','Adaptive procedural renderer','set-quality',[['eco','Eco'],['balanced','Balanced'],['spectacle','Spectacle']],p.quality)}${settingToggle('Desktop orb','Floating presence window','set-desktop-orb',p.desktop_orb)}${settingToggle('Always on top','Keep orb visible','set-top',p.always_on_top)}${settingInput('Orb scale','0.5–2.0','set-scale',p.orb_scale,'number','0.05')}${settingInput('Bloom','0–1','set-bloom',p.bloom,'number','0.05')}</section>
  <section class="setting-card"><h2>Hardware</h2><div class="setting-row"><label>Accelerator policy<small>All routable NPUs first; GPU fallback second; CPU last.</small></label><b>NPU → GPU → CPU</b></div>${settingToggle('CPU fallback','Universal fallback after every NPU/GPU candidate fails','set-cpu-fallback',h.allow_cpu_fallback)}${settingToggle('Reduce visuals under load','Protect inference latency','set-auto-visuals',h.auto_reduce_visuals)}</section>
  <section class="setting-card"><h2>Memory</h2>${settingSelect('Profile','Strict targets the 2–3 GB whole-platform ceiling','set-profile',[['strict','Strict'],['voice','Voice'],['agent','Agent']],m.profile)}${settingToggle('Adaptive pressure','Unload optional workers when Windows is low on memory','set-pressure',m.adaptive_pressure)}</section>
  <section class="setting-card"><h2>Privacy</h2>${settingToggle('Local telemetry only','Never upload system metrics','set-local-telemetry',pr.telemetry_local_only)}${settingToggle('Save transcripts','Persist speech text locally','set-save-transcripts',pr.save_transcripts)}${settingToggle('Save audio','Persist microphone audio locally','set-save-audio',pr.save_audio)}${settingToggle('Cloud context by default','Allow context to cloud agents without per-task opt-in','set-cloud-context',pr.cloud_context_default)}</section>
  <section class="setting-card"><h2>Agents</h2>${settingToggle('Confirm local launches','Require explicit user start unless scheduled','set-confirm-local',ag.confirm_local_launch)}${settingToggle('Confirm cloud launches','Require explicit user start unless scheduled','set-confirm-cloud',ag.confirm_cloud_launch)}${settingToggle('Auto-create Kanban cards','Agent work appears on the board','set-auto-kanban',ag.auto_create_kanban)}${settingInput('Max local coding agents','Strict defaults to one','set-max-agents',ag.max_local_coding_agents,'number','1')}</section>`;
  bindSettings();applyTheme(all);
}
function settingToggle(label,help,id,value){return `<div class="setting-row"><label>${esc(label)}<small>${esc(help)}</small></label><input id="${id}" class="toggle" type="checkbox" ${value?'checked':''}></div>`}
function settingSelect(label,help,id,opts,value){return `<div class="setting-row"><label>${esc(label)}<small>${esc(help)}</small></label><select id="${id}">${opts.map(([v,l])=>`<option value="${v}" ${String(v)===String(value)?'selected':''}>${esc(l)}</option>`).join('')}</select></div>`}
function settingInput(label,help,id,value,type='text',step=''){return `<div class="setting-row"><label>${esc(label)}<small>${esc(help)}</small></label><input id="${id}" type="${type}" ${step?`step="${step}"`:''} value="${esc(value)}"></div>`}
function settingColor(label,help,id,value){return `<div class="setting-row"><label>${esc(label)}<small>${esc(help)}</small></label><input id="${id}" type="color" value="${esc(value)}"></div>`}
async function saveSection(section,values){try{await invoke('settings.set',{section,values});await refreshStatus();toast(`${section} settings saved`)}catch(e){toast(e.message)}}
function bindSettings(){
  const by=id=>$('#'+id);
  ['set-accent','set-gold','set-density','set-motion'].forEach(id=>by(id).onchange=()=>saveSection('appearance',{accent:by('set-accent').value,gold:by('set-gold').value,density:by('set-density').value,reduce_motion:by('set-motion').checked}));
  ['set-quality','set-desktop-orb','set-top','set-scale','set-bloom'].forEach(id=>by(id).onchange=async()=>{const values={quality:by('set-quality').value,desktop_orb:by('set-desktop-orb').checked,always_on_top:by('set-top').checked,orb_scale:Number(by('set-scale').value),bloom:Number(by('set-bloom').value)};await saveSection('presence',values);await nativeWindow(values.desktop_orb?'orb.show':'orb.hide');await nativeWindow('orb.always_on_top',values.always_on_top);await nativeWindow('orb.scale',values.orb_scale)});
  ['set-cpu-fallback','set-auto-visuals'].forEach(id=>by(id).onchange=()=>saveSection('hardware',{device_order:['NPU','GPU','CPU'],all_npus:true,gpu_fallback:true,allow_cpu_fallback:by('set-cpu-fallback').checked,auto_reduce_visuals:by('set-auto-visuals').checked}));
  ['set-profile','set-pressure'].forEach(id=>by(id).onchange=()=>saveSection('memory',{profile:by('set-profile').value,adaptive_pressure:by('set-pressure').checked}));
  ['set-local-telemetry','set-save-transcripts','set-save-audio','set-cloud-context'].forEach(id=>by(id).onchange=()=>saveSection('privacy',{telemetry_local_only:by('set-local-telemetry').checked,save_transcripts:by('set-save-transcripts').checked,save_audio:by('set-save-audio').checked,cloud_context_default:by('set-cloud-context').checked}));
  ['set-confirm-local','set-confirm-cloud','set-auto-kanban','set-max-agents'].forEach(id=>by(id).onchange=()=>saveSection('agents',{confirm_local_launch:by('set-confirm-local').checked,confirm_cloud_launch:by('set-confirm-cloud').checked,auto_create_kanban:by('set-auto-kanban').checked,max_local_coding_agents:Number(by('set-max-agents').value)}));
}
function applyTheme(all){const a=all?.appearance;if(!a)return;const r=document.documentElement.style;r.setProperty('--red',a.accent);r.setProperty('--gold',a.gold);r.setProperty('--bg',a.background||'#090708');}

async function boot(){
  $$('#nav button').forEach(b=>b.onclick=()=>setView(b.dataset.view)); $$('[data-go]').forEach(b=>b.onclick=()=>setView(b.dataset.go));
  $('#refreshBtn').onclick=async()=>{try{await refreshStatus();toast('Refreshed')}catch(e){toast(e.message)}};
  $('#hardwareRefresh').onclick=async()=>{try{await invoke('hardware.refresh');await refreshStatus();renderHardware();toast('Hardware re-scanned')}catch(e){toast(e.message)}};
  $('#winmlCatalog').onclick=async()=>{try{const r=await invoke('hardware.windows_ml_catalog');if(r.error)throw new Error(r.error);const names=(r.providers||[]).map(p=>`${p.name}: ${p.ready_state}${p.version?' '+p.version:''}`).join('\n')||'No compatible Windows ML providers reported.';alert(names)}catch(e){toast(e.message)}};
  $('#winmlEnsure').onclick=async()=>{if(!confirm('Download/register Windows-certified execution providers compatible with this PC? This may use network data.'))return;try{toast('Preparing Windows ML execution providers…');const r=await invoke('hardware.ensure_windows_ml');if(r.error)throw new Error(r.error);await invoke('hardware.refresh');await refreshStatus();renderHardware();toast('Windows ML providers are ready')}catch(e){toast(e.message)}};
  $('#newTaskBtn').onclick=async()=>{const title=prompt('Task title');if(!title)return;try{await invoke('tasks.create',{title,status:'backlog'});renderTasks()}catch(e){toast(e.message)}};
  $('#ttsToggle').onclick=async()=>{const on=!(state.status?.tts?.enabled);try{await invoke('tts.enabled',{enabled:on});await refreshStatus()}catch(e){toast(e.message)}};
  $('#speakBtn').onclick=async()=>{try{await invoke('tts.speak',{text:$('#ttsText').value,priority:3,category:'manual',force:true});toast('Speech queued')}catch(e){toast(e.message)}};
  $('#stopSpeakBtn').onclick=()=>invoke('tts.stop').catch(e=>toast(e.message));
  try{await refreshStatus();applyTheme(state.settings);await renderTasks();await pollEvents()}catch(e){toast(e.message)}
  setInterval(()=>{if(!state.polling){state.polling=true;Promise.allSettled([refreshStatus(),pollEvents()]).finally(()=>state.polling=false)}},2500);
  setInterval(pollEvents,250);
}

document.addEventListener('DOMContentLoaded',boot);
})();
