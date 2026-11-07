(() => {
  'use strict';

  const canvas = document.getElementById('orb');
  const stateLabel = document.getElementById('state');
  const companionRoot = document.getElementById('companions');
  const floating = !new URLSearchParams(location.search).has('dashboard');
  window.__METATRON_FLOATING_ORB__ = floating;

  const gl = canvas.getContext('webgl2', {
    alpha: true,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: true,
    powerPreference: 'low-power',
    preserveDrawingBuffer: false,
  });
  if (!gl) {
    // Companion-only fallback: the product remains usable in Pet mode when
    // WebGL2 is disabled by policy/driver.  We deliberately avoid creating a
    // second renderer; this is the same Presence document using lightweight DOM.
    canvas.hidden = true;
    const fallback = {
      state:'idle', presenceEnabled:true, presenceMode:'orb', desktopPets:true, dashboardPets:true,
      reduceMotion:false, motionStyle:'balanced',
      companions:{enabled:false,reaction_gain:1,pointer_interaction:true,performance_policy:'adaptive',pets:[]},
    };
    const nodes = new Map();
    const slots = [[.28,.30],[.72,.30],[.30,.70],[.70,.70]];
    const makeNode = pet => {
      const node=document.createElement('div'); node.className='companion'; node.dataset.petId=pet.id;
      node.innerHTML='<div class="pet-shadow"></div><div class="pet-trail"></div><div class="pet-body"><span class="pet-core"></span><i class="pet-eye pet-eye-a"></i><i class="pet-eye pet-eye-b"></i><i class="pet-fin pet-fin-a"></i><i class="pet-fin pet-fin-b"></i></div><span class="pet-name"></span>';
      companionRoot.appendChild(node); nodes.set(pet.id,node); return node;
    };
    const allowsPets = () => fallback.presenceEnabled && fallback.companions.enabled && ['pet','both'].includes(fallback.presenceMode) && (floating?fallback.desktopPets:fallback.dashboardPets);
    const sync = () => {
      const pets=Array.isArray(fallback.companions.pets)?fallback.companions.pets.slice(0,4):[];
      const ids=new Set(pets.map(p=>String(p.id||'')));
      for(const [id,node] of [...nodes]) if(!ids.has(id)){node.remove();nodes.delete(id);}
      pets.forEach((pet,index)=>{
        const id=String(pet.id||`pet-${index}`),node=nodes.get(id)||makeNode({...pet,id}),slot=slots[index%slots.length];
        node.dataset.form=pet.form||'flin'; node.dataset.skin=pet.skin||'spectral'; node.dataset.behavior='perch'; node.dataset.anchor=pet.anchor||'free'; node.dataset.state=fallback.state;
        node.style.setProperty('--pet-primary',pet.primary||'#ff8f9c'); node.style.setProperty('--pet-secondary',pet.secondary||'#ffc65c'); node.style.setProperty('--pet-size',String(Math.max(.45,Math.min(1.6,Number(pet.size)||1))));
        node.querySelector('.pet-name').textContent=pet.name||id;
        node.style.transform=`translate(${(slot[0]*innerWidth).toFixed(1)}px,${(slot[1]*innerHeight).toFixed(1)}px) translate(-50%,-50%)`;
        node.hidden=!pet.enabled||!allowsPets();
      });
      stateLabel.textContent = allowsPets() ? `${fallback.state} · companion fallback` : '3D core unavailable';
    };
    const ingest = ev => {
      if(!ev||typeof ev!=='object')return; const topic=ev.topic||'',data=ev.payload||ev;
      if(topic==='presence.customization'||topic==='settings.presence'){
        if(data.enabled!=null)fallback.presenceEnabled=!!data.enabled; if(['orb','pet','both'].includes(data.mode))fallback.presenceMode=data.mode;
        if(data.desktop_pets!=null)fallback.desktopPets=!!data.desktop_pets; if(data.dashboard_pets!=null)fallback.dashboardPets=!!data.dashboard_pets;
        if(data.reduce_motion!=null)fallback.reduceMotion=!!data.reduce_motion; if(data.motion_style)fallback.motionStyle=data.motion_style;
        if(data.companions&&typeof data.companions==='object')fallback.companions={...fallback.companions,...data.companions,pets:Array.isArray(data.companions.pets)?data.companions.pets:fallback.companions.pets};
      }
      if(topic==='presence.state'&&data.state)fallback.state=data.state;
      if(topic==='speech.user.started')fallback.state='listening'; if(topic==='speech.user.ended')fallback.state='transcribing';
      if(topic==='assistant.thinking.started')fallback.state='thinking'; if(topic==='tts.started')fallback.state='speaking'; if(topic==='tts.finished')fallback.state='idle';
      sync();
    };
    addEventListener('resize',sync,{passive:true});
    window.metatronOrb={ingest,state:()=>JSON.parse(JSON.stringify(fallback)),simulateUser:()=>ingest({topic:'speech.user.started',payload:{}}),simulateAI:()=>ingest({topic:'tts.started',payload:{}}),simulateTask:()=>sync(),setVisible:()=>{}};
    sync();
    return;
  }

  const VERT = `#version 300 es
  precision highp float;
  out vec2 vUv;
  void main(){
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    vUv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
  }`;

  const FRAG = `#version 300 es
  precision highp float;
  out vec4 fragColor;
  in vec2 vUv;
  uniform vec2 uResolution;
  uniform float uTime;
  uniform float uUser;
  uniform float uAI;
  uniform float uState;
  uniform float uSignal;
  uniform float uQuality;
  uniform vec2 uPointer;
  uniform vec3 uAccent;
  uniform vec3 uGold;
  uniform float uOrbScale;
  uniform float uBloom;
  uniform float uPlasma;
  uniform float uParticles;
  uniform float uInteractionGain;
  uniform float uOrbOpacity;
  uniform float uCoreStyle;
  uniform float uCorePulse;
  uniform float uCoreRotation;
  uniform float uCoreComplexity;
  uniform float uCoreShell;
  uniform float uTrailStrength;
  uniform float uParallaxStrength;
  uniform float uOrbVisible;

  float hash21(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }
  float hash31(vec3 p){ p=fract(p*.1031); p+=dot(p,p.yzx+33.33); return fract((p.x+p.y)*p.z); }
  float n3(vec3 p){
    vec3 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
    float n000=hash31(i+vec3(0,0,0)), n100=hash31(i+vec3(1,0,0));
    float n010=hash31(i+vec3(0,1,0)), n110=hash31(i+vec3(1,1,0));
    float n001=hash31(i+vec3(0,0,1)), n101=hash31(i+vec3(1,0,1));
    float n011=hash31(i+vec3(0,1,1)), n111=hash31(i+vec3(1,1,1));
    return mix(mix(mix(n000,n100,f.x),mix(n010,n110,f.x),f.y),mix(mix(n001,n101,f.x),mix(n011,n111,f.x),f.y),f.z);
  }
  float fbm(vec3 p){
    float v=0., a=.5; mat3 m=mat3(.00,.80,.60,-.80,.36,-.48,-.60,-.48,.64);
    for(int i=0;i<5;i++){ v+=a*n3(p); p=m*p*2.03+1.7; a*=.5; if(float(i)>uQuality+1.2) break; }
    return v;
  }
  vec3 rotY(vec3 p,float a){float c=cos(a),s=sin(a);return vec3(c*p.x+s*p.z,p.y,-s*p.x+c*p.z);}
  vec3 rotX(vec3 p,float a){float c=cos(a),s=sin(a);return vec3(p.x,c*p.y-s*p.z,s*p.y+c*p.z);}
  float sphereHit(vec3 ro, vec3 rd, float r, out float t0, out float t1){
    float b=dot(ro,rd), c=dot(ro,ro)-r*r, h=b*b-c;
    if(h<0.0){t0=t1=-1.;return 0.;} h=sqrt(h); t0=-b-h; t1=-b+h; return 1.;
  }
  float filament(vec3 p, float phase){
    float r=length(p.xz); float ang=atan(p.z,p.x);
    float y=sin(ang*3.0+uTime*(.55+phase*.12)+phase)*.18;
    float d=abs(p.y-y)+abs(r-.63-.045*sin(ang*5.0-phase+uTime*.23));
    return exp(-32.0*d);
  }
  float lattice(vec3 p){
    vec3 q=p*(7.0+uCoreComplexity*5.0);
    float lines=max(max(abs(sin(q.x)),abs(sin(q.y))),abs(sin(q.z)));
    float cells=pow(lines,18.0);
    float arcs=pow(abs(sin(atan(p.z,p.x)*6.0+uTime*uCoreRotation)),14.0);
    return max(cells*.52,arcs*exp(-3.0*abs(length(p)-.36)));
  }
  float reactor(vec3 p){
    float r=length(p.xz);
    float ring=exp(-55.0*abs(r-(.26+.035*sin(uTime*uCorePulse*2.0))))*exp(-7.0*abs(p.y));
    float spine=exp(-30.0*r)*smoothstep(.5,.05,abs(p.y));
    float petals=pow(.5+.5*cos(atan(p.z,p.x)*6.0+uTime*uCoreRotation*2.2),10.0)*exp(-10.0*abs(r-.38));
    return ring+spine*.8+petals*.5;
  }
  vec3 spectral(vec3 p, float radial){
    float speak=max(uUser,uAI)*uInteractionGain;
    float pulse=1.0+.16*uCorePulse*sin(uTime*(1.4+.8*uCorePulse)+radial*6.0);
    float turbulence=fbm(rotY(p*(3.1+uCoreComplexity*.7),uTime*.12*uCoreRotation)+vec3(0,uTime*.16,0));
    turbulence=mix(.5,turbulence,clamp(uPlasma,0.0,1.5));
    float shellNoise=(turbulence-.5)*(.11+.11*speak);
    float shell=exp(-42.0*abs(radial-(.74+shellNoise)))*uCoreShell;
    float inner=exp(-7.5*radial*radial);
    float solar=exp(-18.0*radial*radial)*pulse;
    float geom=solar;
    if(uCoreStyle>.5 && uCoreStyle<1.5) geom=mix(solar,lattice(p),.88);
    if(uCoreStyle>=1.5) geom=mix(solar,reactor(p),.90);
    float veins=pow(max(0.0,fbm(p*(6.2+uCoreComplexity*2.4)+uTime*.09)-.57),2.0)*4.5*exp(-2.0*radial);
    float rings=(filament(rotX(p,uTime*.09*uCoreRotation),0.0)+filament(rotY(p,-uTime*.11*uCoreRotation),2.2))*uTrailStrength;
    vec3 rose=mix(uAccent,vec3(1.0),.28);
    vec3 whiteGold=mix(uGold,vec3(1.0),.55);
    vec3 col=uAccent*shell*(.75+.85*turbulence);
    col+=rose*inner*.18;
    col+=uGold*veins*(.25+.42*uCoreComplexity);
    col+=uGold*rings*(.40+.7*uAI+.25*uSignal);
    col+=mix(uGold,whiteGold,.42)*geom*(1.18+1.5*uAI+.35*uSignal);
    return col;
  }

  void main(){
    vec2 frag=gl_FragCoord.xy;
    vec2 uv=(frag*2.0-uResolution.xy)/uResolution.y;
    vec2 parallax=(uPointer-.5)*vec2(.12,.08)*uParallaxStrength;
    vec3 ro=vec3(parallax.x,parallax.y,2.75);
    vec3 rd=normalize(vec3(uv,-1.75));
    float active=max(uUser,uAI);
    float breathe=.025*sin(uTime*1.35*uCorePulse)+.018*sin(uTime*.47+1.2);
    float radius=(.78+breathe+.035*active*uInteractionGain)*uOrbScale;
    float t0,t1; float hit=sphereHit(ro,rd,radius,t0,t1);
    vec3 col=vec3(0.0); float alpha=0.0;
    if(hit>0.5 && uOrbVisible>.01){
      float steps=mix(18.0,42.0,clamp(uQuality/2.0,0.0,1.0));
      float dt=(t1-t0)/steps, trans=1.0;
      for(int i=0;i<48;i++){
        if(float(i)>=steps) break;
        float t=t0+(float(i)+.5)*dt;
        vec3 p=ro+rd*t;
        p=rotY(p,uTime*.045*uCoreRotation+uState*.04);
        float r=length(p); vec3 e=spectral(p,r);
        float dens=clamp(length(e)*.12,0.0,.24);
        col+=e*dens*trans*dt*2.0; trans*=1.0-dens*.47;
      }
      vec3 ph=ro+rd*t0; vec3 n=normalize(ph);
      float fres=pow(1.0-max(0.0,dot(n,-rd)),2.5);
      vec3 rim=mix(uAccent,uGold,uAI*.7+uSignal*.3);
      col+=rim*fres*(.42+.9*active*uInteractionGain+.55*uSignal)*uBloom;
      alpha=clamp(1.0-trans+fres*.34,.0,.94);
    }
    float d=length(uv);
    float halo=exp(-8.0*max(0.0,d-radius*.82))*smoothstep(1.25,.28,d)*uOrbVisible;
    col+=uAccent*halo*.075*uBloom; col+=uGold*halo*(.08+.18*uAI+.10*uSignal)*uBloom;
    float wavePhase=uAI>uUser?d*22.0-uTime*6.5:d*22.0+uTime*5.0;
    float wave=pow(max(0.0,.5+.5*cos(wavePhase)),14.0)*exp(-3.5*abs(d-.88))*uTrailStrength*uOrbVisible;
    col+=mix(uAccent,uGold,step(uUser,uAI))*wave*active*uInteractionGain*.35*uBloom;
    vec2 cell=floor((uv+vec2(uTime*.004,-uTime*.006))*55.0);
    float rnd=hash21(cell); vec2 local=fract((uv+vec2(uTime*.004,-uTime*.006))*55.0)-.5;
    float sparkle=smoothstep(.055,0.0,length(local))*step(.995-(.013+.004*uQuality)*clamp(uParticles,0.0,1.5),rnd)*uOrbVisible;
    sparkle*=smoothstep(1.5,.45,d)*(1.0+.8*active);
    col+=mix(uAccent,uGold,rnd)*sparkle*.75*uBloom; alpha=max(alpha,sparkle*.8+halo*.08);
    col=1.0-exp(-col*1.38); col=pow(col,vec3(.82));
    fragColor=vec4(col,clamp(alpha,0.0,.96)*uOrbOpacity*uOrbVisible);
  }`;

  function compile(type, src){
    const shader=gl.createShader(type); gl.shaderSource(shader,src); gl.compileShader(shader);
    if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
    return shader;
  }
  const program=gl.createProgram();
  gl.attachShader(program,compile(gl.VERTEX_SHADER,VERT));
  gl.attachShader(program,compile(gl.FRAGMENT_SHADER,FRAG));
  gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  const U={};
  for(const name of ['uResolution','uTime','uUser','uAI','uState','uSignal','uQuality','uPointer','uAccent','uGold','uOrbScale','uBloom','uPlasma','uParticles','uInteractionGain','uOrbOpacity','uCoreStyle','uCorePulse','uCoreRotation','uCoreComplexity','uCoreShell','uTrailStrength','uParallaxStrength','uOrbVisible']) U[name]=gl.getUniformLocation(program,name);
  gl.bindVertexArray(gl.createVertexArray());

  const states={dormant:0,idle:1,listening:2,transcribing:3,thinking:4,responding:5,speaking:6};
  const quality={eco:{id:0,scale:.52,idle:15,active:30},balanced:{id:1,scale:.72,idle:24,active:60},spectacle:{id:2,scale:1,idle:30,active:60}};
  const coreStyles={solar:0,lattice:1,reactor:2};
  const model={
    state:'idle',quality:'balanced',user:0,ai:0,signal:0,taskPulse:0,pointer:[.5,.5],dashboardOpen:false,
    accent:[1,.24,.31],gold:[1,.69,.16],orbScale:1,bloom:.88,plasma:.82,particles:.78,interactionGain:1,orbOpacity:.96,
    reduceMotion:false,motionStyle:'balanced',presenceEnabled:true,presenceMode:'orb',desktopOrb:true,dashboardOrb:true,desktopPets:true,dashboardPets:true,
    coreStyle:'solar',corePulse:.76,coreRotation:.55,coreComplexity:.82,coreShell:.72,trailStrength:.36,parallaxStrength:.68,
    companions:{enabled:false,reaction_gain:1,pointer_interaction:true,performance_policy:'adaptive',pets:[]},pressureUntil:0,
  };
  let targetUser=0,targetAI=0,lastFrame=0,lastSignalAt=0,lastTaskAt=0,running=true;
  const petNodes=new Map();

  const clamp01=x=>Math.max(0,Math.min(1,Number(x)||0));
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,Number(x)||0));
  function color3(hex,fallback){const m=/^#?([0-9a-f]{6})$/i.exec(String(hex||''));if(!m)return fallback;const n=parseInt(m[1],16);return [((n>>16)&255)/255,((n>>8)&255)/255,(n&255)/255];}
  function surfaceAllowsOrb(){return model.presenceEnabled && ['orb','both'].includes(model.presenceMode) && (floating?model.desktopOrb:model.dashboardOrb);}
  function surfaceAllowsPets(){return model.presenceEnabled && model.companions.enabled && ['pet','both'].includes(model.presenceMode) && (floating?model.desktopPets:model.dashboardPets);}

  function resize(){
    const q=quality[model.quality]||quality.balanced,dpr=Math.min(devicePixelRatio||1,1.6),maxDim=model.quality==='spectacle'?1440:model.quality==='balanced'?1080:720;
    let w=Math.max(1,Math.round(innerWidth*dpr*q.scale)),h=Math.max(1,Math.round(innerHeight*dpr*q.scale));
    const max=Math.max(w,h);if(max>maxDim){const k=maxDim/max;w=Math.round(w*k);h=Math.round(h*k);}
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
  }
  addEventListener('resize',resize,{passive:true}); resize();

  function makePetNode(pet){
    const node=document.createElement('div');node.className='companion';node.dataset.petId=pet.id;
    node.innerHTML='<div class="pet-shadow"></div><div class="pet-trail"></div><div class="pet-body"><span class="pet-core"></span><i class="pet-eye pet-eye-a"></i><i class="pet-eye pet-eye-b"></i><i class="pet-fin pet-fin-a"></i><i class="pet-fin pet-fin-b"></i></div><span class="pet-name"></span>';
    companionRoot.appendChild(node);petNodes.set(pet.id,node);return node;
  }
  function syncCompanions(){
    const pets=Array.isArray(model.companions.pets)?model.companions.pets.slice(0,4):[],ids=new Set(pets.map(p=>String(p.id||'')));
    for(const [id,node] of [...petNodes])if(!ids.has(id)){node.remove();petNodes.delete(id);}
    pets.forEach((pet,index)=>{
      const id=String(pet.id||`pet-${index}`),node=petNodes.get(id)||makePetNode({...pet,id});
      node.dataset.form=pet.form||'flin';node.dataset.skin=pet.skin||'spectral';node.dataset.behavior=pet.behavior||'orbit';node.dataset.anchor=pet.anchor||'free';
      node.style.setProperty('--pet-primary',pet.primary||'#ff8f9c');node.style.setProperty('--pet-secondary',pet.secondary||'#ffc65c');node.style.setProperty('--pet-size',String(clamp(pet.size,.45,1.6)));
      node.querySelector('.pet-name').textContent=pet.name||id;node.hidden=!pet.enabled||!surfaceAllowsPets();
    });
  }
  function anchorPoint(anchor,index){
    const pad=.17;switch(anchor){case'upper-left':return[pad,pad];case'upper-right':return[1-pad,pad];case'lower-left':return[pad,1-pad];case'lower-right':return[1-pad,1-pad];default:return[.5,.5];}
  }
  function updateCompanions(now){
    const pets=Array.isArray(model.companions.pets)?model.companions.pets.slice(0,4):[];
    let visible=pets.filter(p=>p.enabled&&surfaceAllowsPets());
    const pressured=performance.now()<model.pressureUntil||model.quality==='eco';
    if(model.companions.performance_policy==='minimal'||(model.companions.performance_policy==='adaptive'&&pressured)) visible=visible.slice(0,1);
    const activeIds=new Set(visible.map(p=>p.id));
    petNodes.forEach((node,id)=>{node.hidden=!activeIds.has(id);});
    const t=now*.001,react=(model.user+model.ai+model.signal*.7+model.taskPulse*.55)*clamp(model.companions.reaction_gain,0,2);
    visible.forEach((pet,index)=>{
      const node=petNodes.get(pet.id);if(!node)return;
      const energy=clamp(pet.energy,0,1.5),voice=clamp(pet.voice_reactivity,0,1.5),task=clamp(pet.task_reactivity,0,1.5);
      const reduce=model.reduceMotion||model.motionStyle==='minimal';
      const reducedSlots=[[.32,.34],[.68,.34],[.34,.68],[.66,.68]];
      const anchor=(reduce&&pet.anchor==='free')?reducedSlots[index%reducedSlots.length]:anchorPoint(pet.anchor,index);
      let x=anchor[0],y=anchor[1],angle=0;
      if(!reduce&&pet.behavior==='orbit'){
        const a=t*(.34+.38*energy)+index*1.71+(model.ai-model.user)*.5;
        const r=.27+index*.035;x=.5+Math.cos(a)*r;y=.5+Math.sin(a)*r*.74;angle=a+1.57;
      }else if(!reduce&&pet.behavior==='drift'){
        x=anchor[0]+Math.sin(t*(.46+.2*energy)+index*2.4)*.18;y=anchor[1]+Math.cos(t*(.39+.16*energy)+index)*.12;angle=Math.sin(t*.5+index)*.22;
      }else if(!reduce&&pet.behavior==='pointer'&&model.companions.pointer_interaction){
        x=.22+model.pointer[0]*.56+Math.sin(t*1.2+index)*.025;y=.22+(1-model.pointer[1])*.56+Math.cos(t*.9+index)*.02;angle=(model.pointer[0]-.5)*.35;
      }else if(!reduce&&pet.behavior==='perch'){
        x=anchor[0]+Math.sin(t*.75+index)*.018;y=anchor[1]+Math.sin(t*(1.2+energy*.3)+index)*.025;angle=Math.sin(t*.55+index)*.10;
      }
      const bob=reduce?0:Math.sin(t*(1.8+energy)+index*2.2)*(.008+.014*energy),boost=1+react*(.025+.04*voice)+model.taskPulse*.05*task;
      x=clamp(x,.08,.92);y=clamp(y+bob,.08,.92);
      node.style.transform=`translate(${(x*innerWidth).toFixed(2)}px,${(y*innerHeight).toFixed(2)}px) translate(-50%,-50%) rotate(${angle.toFixed(3)}rad) scale(${boost.toFixed(3)})`;
      node.style.setProperty('--pet-energy',String(energy));node.style.setProperty('--pet-react',String(clamp(react*voice,0,1.5)));node.style.setProperty('--pet-task',String(clamp(model.taskPulse*task,0,1.5)));node.dataset.state=model.state;
    });
  }

  function setQuality(q){if(!quality[q])return;model.quality=q;resize();stateLabel.textContent=`${model.state} · ${model.quality}`;}
  function applyCustomization(p={}){
    if(p.accent)model.accent=color3(p.accent,model.accent);if(p.gold)model.gold=color3(p.gold,model.gold);
    if(p.enabled!=null)model.presenceEnabled=!!p.enabled;if(['orb','pet','both'].includes(p.mode))model.presenceMode=p.mode;
    if(p.desktop_orb!=null)model.desktopOrb=!!p.desktop_orb;if(p.dashboard_orb!=null)model.dashboardOrb=!!p.dashboard_orb;if(p.desktop_pets!=null)model.desktopPets=!!p.desktop_pets;if(p.dashboard_pets!=null)model.dashboardPets=!!p.dashboard_pets;
    if(p.orb_scale!=null)model.orbScale=clamp(p.orb_scale,.5,2);if(p.bloom!=null)model.bloom=clamp(p.bloom,0,1.5);if(p.plasma!=null)model.plasma=clamp(p.plasma,0,1.5);if(p.particles!=null)model.particles=clamp(p.particles,0,1.5);if(p.interaction_gain!=null)model.interactionGain=clamp(p.interaction_gain,.1,3);if(p.orb_opacity!=null)model.orbOpacity=clamp(p.orb_opacity,.1,1);
    if(['solar','lattice','reactor'].includes(p.core_style))model.coreStyle=p.core_style;if(p.core_pulse!=null)model.corePulse=clamp(p.core_pulse,0,2);if(p.core_rotation!=null)model.coreRotation=clamp(p.core_rotation,0,2);if(p.core_complexity!=null)model.coreComplexity=clamp(p.core_complexity,0,1.5);if(p.core_shell!=null)model.coreShell=clamp(p.core_shell,0,1.5);if(p.trail_strength!=null)model.trailStrength=clamp(p.trail_strength,0,1.5);if(p.parallax_strength!=null)model.parallaxStrength=clamp(p.parallax_strength,0,1.5);
    if(p.reduce_motion!=null)model.reduceMotion=!!p.reduce_motion;if(['minimal','balanced','expressive'].includes(p.motion_style))model.motionStyle=p.motion_style;if(p.quality)setQuality(p.quality);
    if(p.companions&&typeof p.companions==='object')model.companions={...model.companions,...p.companions,pets:Array.isArray(p.companions.pets)?p.companions.pets:model.companions.pets};
    syncCompanions();
  }
  function ingest(ev){
    if(!ev||typeof ev!=='object')return;const topic=ev.topic||'',p=ev.payload||ev;
    if(topic==='presence.state'&&p.state)model.state=p.state;if(topic==='presence.quality')setQuality(p.quality);
    if(topic==='presence.context'){model.dashboardOpen=!!p.dashboard_open;if(p.desktop_mode==='eco'&&floating)setQuality('eco');}
    if(topic==='presence.customization'||topic==='settings.presence')applyCustomization(p);
    if(topic==='speech.user.started'){model.state='listening';}if(topic==='speech.user.level'||(topic==='presence.level'&&p.channel==='user'))targetUser=clamp01(p.level);if(topic==='speech.user.ended'){targetUser=0;model.state='transcribing';}
    if(topic==='assistant.thinking.started')model.state='thinking';if(topic==='assistant.thinking.finished')model.state='responding';if(topic==='tts.started')model.state='speaking';if(topic==='tts.level'||(topic==='presence.level'&&p.channel==='ai'))targetAI=clamp01(p.level);if(topic==='tts.finished'){targetAI=0;model.state='idle';}
    if(topic==='presence.signal'){model.signal=1;lastSignalAt=performance.now();}
    if(topic.startsWith('task.')||topic.startsWith('run.')||topic.startsWith('approval.')){model.taskPulse=1;lastTaskAt=performance.now();}
    if(topic==='memory.pressure')model.pressureUntil=performance.now()+30000;
    stateLabel.textContent=`${model.state} · ${model.quality}`;
  }

  function frame(now){
    if(!running){requestAnimationFrame(frame);return;}
    const q=quality[model.quality]||quality.balanced,active=(model.state!=='idle'&&model.state!=='dormant')||targetUser>.01||targetAI>.01||model.signal>.02||model.taskPulse>.02;
    const motionFps=model.reduceMotion?{idle:8,active:24}:model.motionStyle==='minimal'?{idle:12,active:36}:{idle:q.idle,active:q.active};const fps=active?motionFps.active:motionFps.idle;
    if(now-lastFrame<1000/fps){requestAnimationFrame(frame);return;}lastFrame=now;
    model.user+=(targetUser-model.user)*.22;model.ai+=(targetAI-model.ai)*.24;targetUser*=.94;targetAI*=.94;if(now-lastSignalAt>120)model.signal*=.91;if(now-lastTaskAt>120)model.taskPulse*=.92;
    resize();const motionScale=model.reduceMotion?.12:(model.motionStyle==='minimal'?.62:model.motionStyle==='expressive'?1.16:1),orbVisible=surfaceAllowsOrb()?1:0;
    gl.uniform2f(U.uResolution,canvas.width,canvas.height);gl.uniform1f(U.uTime,now*.001*motionScale);gl.uniform1f(U.uUser,model.user);gl.uniform1f(U.uAI,model.ai);gl.uniform1f(U.uState,states[model.state]??1);gl.uniform1f(U.uSignal,model.signal);gl.uniform1f(U.uQuality,q.id);gl.uniform2f(U.uPointer,model.pointer[0],model.pointer[1]);gl.uniform3f(U.uAccent,...model.accent);gl.uniform3f(U.uGold,...model.gold);
    gl.uniform1f(U.uOrbScale,model.orbScale);gl.uniform1f(U.uBloom,model.bloom);gl.uniform1f(U.uPlasma,model.plasma);gl.uniform1f(U.uParticles,model.particles);gl.uniform1f(U.uInteractionGain,model.interactionGain);gl.uniform1f(U.uOrbOpacity,model.orbOpacity);gl.uniform1f(U.uCoreStyle,coreStyles[model.coreStyle]??0);gl.uniform1f(U.uCorePulse,model.corePulse);gl.uniform1f(U.uCoreRotation,model.coreRotation);gl.uniform1f(U.uCoreComplexity,model.coreComplexity);gl.uniform1f(U.uCoreShell,model.coreShell);gl.uniform1f(U.uTrailStrength,model.trailStrength);gl.uniform1f(U.uParallaxStrength,model.parallaxStrength);gl.uniform1f(U.uOrbVisible,orbVisible);
    gl.drawArrays(gl.TRIANGLES,0,3);updateCompanions(now);requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  addEventListener('pointermove',e=>{model.pointer=[e.clientX/Math.max(1,innerWidth),1-e.clientY/Math.max(1,innerHeight)];},{passive:true});
  document.addEventListener('visibilitychange',()=>{running=!document.hidden;});
  function pulseAI(){ingest({topic:'tts.started',payload:{}});let t=0;const id=setInterval(()=>{t+=.08;ingest({topic:'tts.level',payload:{level:.2+.7*Math.abs(Math.sin(t*5.1))*Math.abs(Math.sin(t*1.7))}});if(t>2.6){clearInterval(id);ingest({topic:'tts.finished',payload:{}});}},80);}
  function pulseUser(){ingest({topic:'speech.user.started',payload:{}});let t=0;const id=setInterval(()=>{t+=.08;ingest({topic:'speech.user.level',payload:{level:.12+.65*Math.abs(Math.sin(t*4.2))}});if(t>2.1){clearInterval(id);ingest({topic:'speech.user.ended',payload:{}});setTimeout(()=>ingest({topic:'presence.state',payload:{state:'idle'}}),650);}},80);}
  function pulseTask(){ingest({topic:'task.created',payload:{}});}
  canvas.addEventListener('click',e=>{if(e.altKey)pulseTask();else e.shiftKey?pulseAI():pulseUser();});
  syncCompanions();
  window.metatronOrb={ingest,setQuality,applyCustomization,snapshot:()=>JSON.parse(JSON.stringify(model)),simulateUser:pulseUser,simulateAI:pulseAI,simulateTask:pulseTask,setVisible:v=>{running=!!v;}};
})();
