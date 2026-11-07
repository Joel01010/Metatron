(async()=>{
  const tauri=window.__TAURI__;
  const invoke=(cmd,params={})=>tauri?.core?.invoke('backend_command',{cmd,params});
  const syncCustomization=async()=>{
    if(!invoke)return;
    try{
      const [presence,appearance,companions]=await Promise.all([
        invoke('settings.get',{section:'presence'}),
        invoke('settings.get',{section:'appearance'}),
        invoke('settings.get',{section:'companions'}),
      ]);
      window.metatronOrb?.ingest({
        topic:'presence.customization',
        payload:{
          ...(presence||{}),
          accent:appearance?.accent,
          gold:appearance?.gold,
          reduce_motion:!!appearance?.reduce_motion,
          motion_style:appearance?.motion_style||'balanced',
          companions:companions||{},
        },
      });
    }catch{}
  };
  const ingest=ev=>{
    if(!ev||typeof ev!=='object')return;
    window.metatronOrb?.ingest(ev);
    if((ev.topic==='settings.changed'||ev.topic==='settings.reset')&&
       (!ev.payload?.section||['appearance','presence','companions'].includes(ev.payload.section))){
      syncCustomization();
    }
  };
  window.addEventListener('message',e=>{
    const ev=e.data?.metatronEvent;
    if(ev)ingest(ev);
  });
  if(tauri?.event?.listen){
    await tauri.event.listen('metatron-event',e=>ingest(e.payload));
  }
  const visibility=()=>invoke?.('bridge.live_events',{enabled:!document.hidden,consumer:'orb'})?.catch?.(()=>{});
  document.addEventListener('visibilitychange',visibility); visibility();
  try{
    const state=await invoke('presence.renderer_state');
    if(state)ingest({topic:'presence.state',payload:state});
    await syncCustomization();
  }catch{}
  document.getElementById('orb').addEventListener('dblclick',()=>tauri?.core?.invoke('window_command',{action:'main.show',value:null}));
})();
