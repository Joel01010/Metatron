(async()=>{
  const tauri=window.__TAURI__;
  const invoke=(cmd,params={})=>tauri?.core?.invoke('backend_command',{cmd,params});
  if(tauri?.event?.listen){
    await tauri.event.listen('metatron-event',e=>window.metatronOrb?.ingest(e.payload));
  }
  const visibility=()=>invoke('bridge.live_events',{enabled:!document.hidden,consumer:'orb'}).catch(()=>{});
  document.addEventListener('visibilitychange',visibility); visibility();
  try{
    const [state,settings]=await Promise.all([invoke('presence.renderer_state'),invoke('settings.get',{section:'presence'})]);
    if(state)window.metatronOrb?.ingest({topic:'presence.state',payload:state});
    let appearance={}; try{appearance=await invoke('settings.get',{section:'appearance'})||{}}catch{}
    if(settings)window.metatronOrb?.ingest({topic:'presence.customization',payload:{...settings,accent:appearance.accent,gold:appearance.gold}});
  }catch{}
  document.getElementById('orb').addEventListener('dblclick',()=>tauri?.core?.invoke('window_command',{action:'main.show',value:null}));
})();
