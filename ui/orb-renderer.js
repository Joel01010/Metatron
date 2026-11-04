(() => {
  'use strict';

  const canvas = document.getElementById('orb');
  const stateLabel = document.getElementById('state');
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
    document.body.innerHTML = '<div style="padding:20px">WebGL2 is required for the Metatron orb.</div>';
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

  #define PI 3.14159265359
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
    float y = sin(ang*3.0 + uTime*(.55+phase*.12) + phase)*.18;
    float d=abs(p.y-y) + abs(r-.63-.045*sin(ang*5.0-phase+uTime*.23));
    return exp(-32.0*d);
  }

  vec3 spectral(vec3 p, float radial){
    float speak=max(uUser,uAI);
    float turbulence=fbm(rotY(p*3.3,uTime*.12)+vec3(0,uTime*.16,0));
    float shellNoise=(turbulence-.5)*(.11+.11*speak);
    float shell=exp(-42.0*abs(radial-(.74+shellNoise)));
    float inner=exp(-7.5*radial*radial);
    float core=exp(-18.0*radial*radial)*(1.0+.55*uAI+.35*uSignal);
    float veins=pow(max(0.0,fbm(p*6.5+uTime*.09)-.57),2.0)*4.5*exp(-2.0*radial);
    float rings=filament(rotX(p,uTime*.09),0.0)+filament(rotY(p,-uTime*.11),2.2);
    vec3 paleRed=vec3(1.0,.24,.31);
    vec3 rose=vec3(1.0,.47,.50);
    vec3 gold=vec3(1.0,.69,.16);
    vec3 whiteGold=vec3(1.0,.91,.58);
    vec3 col=paleRed*shell*(.75+.85*turbulence);
    col+=rose*inner*.18;
    col+=gold*veins*.52;
    col+=gold*rings*(.55+.7*uAI+.25*uSignal);
    col+=mix(gold,whiteGold,.42)*core*(1.4+1.5*uAI);
    return col;
  }

  void main(){
    vec2 frag=gl_FragCoord.xy;
    vec2 uv=(frag*2.0-uResolution.xy)/uResolution.y;
    float aspect=uResolution.x/uResolution.y;
    vec2 parallax=(uPointer-.5)*vec2(.12,.08);
    vec3 ro=vec3(parallax.x,parallax.y,2.75);
    vec3 rd=normalize(vec3(uv,-1.75));

    float active=max(uUser,uAI);
    float breathe=.025*sin(uTime*1.35)+.018*sin(uTime*.47+1.2);
    float radius=.78+breathe+.035*active;
    float t0,t1; float hit=sphereHit(ro,rd,radius,t0,t1);

    vec3 col=vec3(0.0); float alpha=0.0;
    if(hit>0.5){
      float steps=mix(18.0,42.0,clamp(uQuality/2.0,0.0,1.0));
      float dt=(t1-t0)/steps;
      float trans=1.0;
      for(int i=0;i<48;i++){
        if(float(i)>=steps) break;
        float t=t0+(float(i)+.5)*dt;
        vec3 p=ro+rd*t;
        p=rotY(p,uTime*.045+uState*.04);
        float r=length(p);
        vec3 e=spectral(p,r);
        float dens=clamp(length(e)*.12,0.0,.24);
        col += e*dens*trans*dt*2.0;
        trans*=1.0-dens*.47;
      }
      vec3 ph=ro+rd*t0; vec3 n=normalize(ph);
      float fres=pow(1.0-max(0.0,dot(n,-rd)),2.5);
      vec3 rim=mix(vec3(1.0,.26,.32),vec3(1.0,.71,.20),uAI*.7+uSignal*.3);
      col += rim*fres*(.42+.9*active+.55*uSignal);
      alpha=clamp(1.0-trans+fres*.34,.0,.94);
    }

    float d=length(uv);
    float halo=exp(-8.0*max(0.0,d-radius*.82))*smoothstep(1.25,.28,d);
    col += vec3(1.0,.21,.28)*halo*.075;
    col += vec3(1.0,.66,.16)*halo*(.08+.18*uAI+.10*uSignal);

    // Shock waves: user speech contracts inward; AI speech radiates outward.
    float wavePhase = uAI>uUser ? d*22.0-uTime*6.5 : d*22.0+uTime*5.0;
    float wave=pow(max(0.0,.5+.5*cos(wavePhase)),14.0)*exp(-3.5*abs(d-.88));
    col += mix(vec3(1.,.23,.31),vec3(1.,.72,.22),step(uUser,uAI))*wave*active*.35;

    // Procedural sparkle field. No particle buffers, allocations or textures.
    vec2 cell=floor((uv+vec2(uTime*.004,-uTime*.006))*55.0);
    float rnd=hash21(cell); vec2 local=fract((uv+vec2(uTime*.004,-uTime*.006))*55.0)-.5;
    float sparkle=smoothstep(.055,0.0,length(local))*step(.982-0.006*uQuality,rnd);
    sparkle*=smoothstep(1.5,.45,d)*(1.0+.8*active);
    col += mix(vec3(1.,.34,.38),vec3(1.,.82,.34),rnd)*sparkle*.75;
    alpha=max(alpha,sparkle*.8+halo*.08);

    // Filmic shoulder without a post-process framebuffer/bloom chain.
    col=1.0-exp(-col*1.38);
    col=pow(col,vec3(.82));
    fragColor=vec4(col,clamp(alpha,0.0,.96));
  }`;

  function compile(type, src){
    const s=gl.createShader(type); gl.shaderSource(s,src); gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }
  const program=gl.createProgram();
  gl.attachShader(program,compile(gl.VERTEX_SHADER,VERT));
  gl.attachShader(program,compile(gl.FRAGMENT_SHADER,FRAG));
  gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  const U={};
  for(const n of ['uResolution','uTime','uUser','uAI','uState','uSignal','uQuality','uPointer']) U[n]=gl.getUniformLocation(program,n);
  const vao=gl.createVertexArray(); gl.bindVertexArray(vao);

  const states={dormant:0,idle:1,listening:2,transcribing:3,thinking:4,responding:5,speaking:6};
  const quality={
    eco:{id:0,scale:.52,idle:15,active:30},
    balanced:{id:1,scale:.72,idle:24,active:60},
    spectacle:{id:2,scale:1.0,idle:30,active:60},
  };
  const model={state:'idle',quality:'balanced',user:0,ai:0,signal:0,pointer:[.5,.5],dashboardOpen:false};
  let targetUser=0,targetAI=0,lastFrame=0,lastSignalAt=0,running=true;

  function resize(){
    const q=quality[model.quality]||quality.balanced;
    const dpr=Math.min(devicePixelRatio||1,1.6);
    const maxDim=model.quality==='spectacle'?1440:model.quality==='balanced'?1080:720;
    let w=Math.max(1,Math.round(innerWidth*dpr*q.scale)), h=Math.max(1,Math.round(innerHeight*dpr*q.scale));
    const m=Math.max(w,h); if(m>maxDim){const k=maxDim/m;w=Math.round(w*k);h=Math.round(h*k);}
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
  }
  addEventListener('resize',resize,{passive:true}); resize();

  function ingest(ev){
    if(!ev||typeof ev!=='object') return;
    const topic=ev.topic||''; const p=ev.payload||ev;
    if(topic==='presence.state'){ if(p.state) model.state=p.state; }
    if(topic==='presence.quality'){ setQuality(p.quality); }
    if(topic==='presence.context'){ model.dashboardOpen=!!p.dashboard_open; if(p.desktop_mode==='eco'&&window.__METATRON_FLOATING_ORB__) setQuality('eco'); }
    if(topic==='speech.user.started'){ model.state='listening'; }
    if(topic==='speech.user.level'||(topic==='presence.level'&&p.channel==='user')) targetUser=clamp01(p.level);
    if(topic==='speech.user.ended'){ targetUser=0; model.state='transcribing'; }
    if(topic==='assistant.thinking.started'){ model.state='thinking'; }
    if(topic==='assistant.thinking.finished'){ model.state='responding'; }
    if(topic==='tts.started'){ model.state='speaking'; }
    if(topic==='tts.level'||(topic==='presence.level'&&p.channel==='ai')) targetAI=clamp01(p.level);
    if(topic==='tts.finished'){ targetAI=0; model.state='idle'; }
    if(topic==='presence.signal'){ model.signal=1; lastSignalAt=performance.now(); }
    stateLabel.textContent=`${model.state} · ${model.quality}`;
  }
  function setQuality(q){ if(!quality[q]) return; model.quality=q; resize(); stateLabel.textContent=`${model.state} · ${model.quality}`; }
  function clamp01(x){x=Number(x)||0;return Math.max(0,Math.min(1,x));}

  function frame(now){
    if(!running){requestAnimationFrame(frame);return;}
    const q=quality[model.quality]||quality.balanced;
    const active=(model.state!=='idle'&&model.state!=='dormant')||targetUser>.01||targetAI>.01||model.signal>.02;
    const fps=active?q.active:q.idle;
    if(now-lastFrame<1000/fps){requestAnimationFrame(frame);return;} lastFrame=now;
    model.user += (targetUser-model.user)*.22;
    model.ai += (targetAI-model.ai)*.24;
    targetUser*=.94; targetAI*=.94;
    if(now-lastSignalAt>120) model.signal*=.91;
    resize();
    gl.uniform2f(U.uResolution,canvas.width,canvas.height);
    gl.uniform1f(U.uTime,now*.001);
    gl.uniform1f(U.uUser,model.user);
    gl.uniform1f(U.uAI,model.ai);
    gl.uniform1f(U.uState,states[model.state]??1);
    gl.uniform1f(U.uSignal,model.signal);
    gl.uniform1f(U.uQuality,q.id);
    gl.uniform2f(U.uPointer,model.pointer[0],model.pointer[1]);
    gl.drawArrays(gl.TRIANGLES,0,3);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  addEventListener('pointermove',e=>{model.pointer=[e.clientX/innerWidth,1-e.clientY/innerHeight];},{passive:true});
  document.addEventListener('visibilitychange',()=>{running=!document.hidden;});

  // Demo interaction. Tauri host can remove/ignore this and call ingest().
  function pulseAI(){ ingest({topic:'tts.started',payload:{}}); let t=0; const id=setInterval(()=>{t+=.08; ingest({topic:'tts.level',payload:{level:.2+.7*Math.abs(Math.sin(t*5.1))*Math.abs(Math.sin(t*1.7))}}); if(t>2.6){clearInterval(id);ingest({topic:'tts.finished',payload:{}});}},80); }
  function pulseUser(){ ingest({topic:'speech.user.started',payload:{}}); let t=0; const id=setInterval(()=>{t+=.08; ingest({topic:'speech.user.level',payload:{level:.12+.65*Math.abs(Math.sin(t*4.2))}}); if(t>2.1){clearInterval(id);ingest({topic:'speech.user.ended',payload:{}});setTimeout(()=>ingest({topic:'presence.state',payload:{state:'idle'}}),650);}},80); }
  canvas.addEventListener('click',e=>{e.shiftKey?pulseAI():pulseUser();});

  window.metatronOrb={
    ingest,
    setQuality,
    snapshot:()=>({...model}),
    simulateUser:pulseUser,
    simulateAI:pulseAI,
    setVisible:v=>{running=!!v;},
  };
})();
