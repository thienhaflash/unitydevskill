<title>__TITLE__</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=Hanken+Grotesk:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one build selector drives a per-__UNIT__ bar chart; below it every __UNIT__'s fps across builds, then what each change measured. */
:root{
  --bg:#f3f5f1; --panel:#ffffff; --ink:#15201b; --muted:#5d6b64; --line:#dde3dd;
  --accent:#0b8f6a; --lv1:#7c9fb8; --lv2:#0b8f6a; --lv3:#c0702f; --good:#13a36e; --warn:#d99a00; --bad:#d6453d; --track:#e6ebe6; --chip:#eaf0ea;
  --display:"Bricolage Grotesque","Trebuchet MS",sans-serif; --body:"Hanken Grotesk",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-__UNIT__="light"]){
  --bg:#0d1512; --panel:#14201b; --ink:#e6efe9; --muted:#8fa399; --line:#22332b;
  --accent:#3fd6a0; --good:#3fd6a0; --warn:#f0b429; --bad:#ff6b5e; --track:#1d2d26; --chip:#1a2a23; --lv1:#7fa6c0; --lv2:#3fd6a0; --lv3:#e39a5b; color-scheme:dark}}
:root[data-__UNIT__="dark"]{
  --bg:#0d1512; --panel:#14201b; --ink:#e6efe9; --muted:#8fa399; --line:#22332b;
  --accent:#3fd6a0; --good:#3fd6a0; --warn:#f0b429; --bad:#ff6b5e; --track:#1d2d26; --chip:#1a2a23; --lv1:#7fa6c0; --lv2:#3fd6a0; --lv3:#e39a5b; color-scheme:dark}
body{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.5;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:28px 56px}
.wrap{max-width:900px;margin:0 auto;display:flex;flex-direction:column;gap:22px}
h1{font-family:var(--display);font-size:clamp(28px,5vw,40px);line-height:1.1;margin:0;text-wrap:balance}
h2{font-family:var(--display);font-size:22px;margin:0 0 4px;text-wrap:balance}
p{margin:0}
.sub{color:var(--muted);max-width:62ch}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;min-width:0}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.tile{background:var(--chip);border-radius:10px;padding:12px 14px}
.tile b{display:block;font-family:var(--display);font-size:28px;line-height:1.1}
.tile span{color:var(--muted);font-size:13px}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.seg{display:flex;flex-wrap:wrap;gap:6px}
.seg button{font:inherit;font-family:var(--mono);font-size:13px;color:var(--ink);background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:6px 12px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--panel);font-weight:500}
.seg button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.desc{margin-top:10px;color:var(--muted);font-size:14px;max-width:70ch}
.row{display:grid;grid-template-columns:64px 1fr 118px;align-items:center;gap:10px;padding:5px 0}
.row .name{font-weight:600}
.track{position:relative;height:22px;background:var(--track);border-radius:6px}
.bar{position:absolute;inset:0 auto 0 0;border-radius:6px;transition:width .35s ease}
.tgt{position:absolute;top:-3px;bottom:-3px;border-left:2px dashed var(--muted)}
.ghost{position:absolute;top:2px;bottom:2px;width:3px;background:var(--ink);opacity:.55;border-radius:2px}
.val{font-family:var(--mono);font-size:13px;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.up{color:var(--good)} .down{color:var(--bad)} .flat{color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:14px;color:var(--muted);font-size:13px;margin-top:12px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.small{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-top:12px}
.sm{border:1px solid var(--line);border-radius:10px;padding:10px 10px 6px;min-width:0}
.sm header{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.sm b{font-weight:600}
.sm svg{display:block;width:100%;height:70px;margin-top:4px}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:560px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
th{font-family:var(--mono);font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:500}
.pill{display:inline-block;font-family:var(--mono);font-size:12px;border-radius:999px;padding:2px 9px;background:var(--chip);white-space:nowrap}
.pill.kept{background:color-mix(in srgb,var(--good) 22%,transparent);color:var(--good)}
.pill.no{background:color-mix(in srgb,var(--bad) 18%,transparent);color:var(--bad)}
.pill.try{background:color-mix(in srgb,var(--warn) 24%,transparent);color:var(--warn)}
.ab{display:grid;grid-template-columns:70px 1fr 90px;gap:10px;align-items:center;padding:4px 0}
.ab .track{height:16px}
.fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:14px;margin-top:16px}
.th{border:1px solid var(--line);border-radius:12px;padding:12px 12px 8px;min-width:0}
.th header{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap}
.th header b{font-family:var(--display);font-size:18px}
.th table{min-width:0;font-size:13px}
.th th,.th td{padding:5px 6px;font-size:13px;white-space:nowrap}
.th td.f{font-family:var(--mono);font-variant-numeric:tabular-nums}
.th tr.sep td,.th tr.sep th{border-top:2px solid var(--line)}
.on{color:var(--good);font-weight:600} .off{color:var(--muted)}
@media (max-width:480px){.row{grid-template-columns:54px 1fr 96px}.card{padding:14px}}
@media (prefers-reduced-motion:reduce){.bar{transition:none}}
.pick{display:flex;flex-direction:column;gap:6px;margin-top:14px;max-width:260px}
.pick select{font:inherit;font-family:var(--body);font-size:15px;padding:8px 10px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
details.hist>summary{cursor:pointer;list-style:none}
details.hist>summary::-webkit-details-marker{display:none}
details.hist>summary h2{display:inline}
details.hist>summary::after{content:" (show)";color:var(--muted);font-size:13px}
details.hist[open]>summary::after{content:" (hide)"}
#final table{min-width:520px}
#final th,#final td{padding:6px 8px;font-size:13px;white-space:nowrap}
#final td.f{font-family:var(--mono);font-variant-numeric:tabular-nums}
#final tr.grp td{font-family:var(--mono);font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);border-top:2px solid var(--line);padding-top:12px}
.frow{display:grid;grid-template-columns:minmax(120px,210px) 1fr 74px;align-items:center;gap:10px;padding:4px 0}
.frow .nm{font-size:14px}
.chart{width:100%;height:auto;display:block;margin-top:6px}
.chart text{font-family:var(--mono);font-size:11px;fill:var(--muted)}
.chart .v{fill:var(--ink)} .chart .slow{fill:var(--bad)}
.lgd{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--muted);margin-top:10px}
.lgd i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.blk{margin-top:20px} .blk h3{font-family:var(--display);font-size:16px;margin:0 0 2px}
@media (max-width:480px){.frow{grid-template-columns:1fr 70px}.frow .track{grid-column:1/3;order:3}}
.ctl{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-end;margin-top:14px}
.ctl .pick{margin-top:0}
.chk{display:flex;align-items:center;gap:8px;font-size:14px;padding-bottom:6px;cursor:pointer}
.chk input{width:18px;height:18px;accent-color:var(--accent)}
.chk small{color:var(--muted)}
.shotrow{display:flex;gap:12px;overflow-x:auto;padding:14px 2px 10px;scroll-snap-type:x proximity;-webkit-overflow-scrolling:touch}
.shotitem{flex:0 0 auto;width:210px;display:flex;flex-direction:column;gap:6px;scroll-snap-align:start;background:none;border:0;padding:0;color:inherit;font:inherit;text-align:left;cursor:zoom-in}
.shotitem img{display:block;width:210px;height:auto;aspect-ratio:1080/2408;object-fit:cover;border-radius:10px;border:1px solid var(--line);background:var(--chip)}
.shotitem span{font-family:var(--mono);font-size:12px;letter-spacing:.04em;color:var(--muted)}
.zoom{position:fixed;inset:0;z-index:50;background:color-mix(in srgb,var(--bg) 88%,#000);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:max(16px,env(safe-area-inset-top,0px)) max(16px,env(safe-area-inset-right,0px)) max(16px,env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px));cursor:zoom-out}
.zoom[hidden]{display:none}
.zoom img{max-width:100%;max-height:calc(100vh - 110px);width:auto;height:auto;border-radius:12px;box-shadow:0 8px 40px rgba(0,0,0,.45)}
.zcap{font-family:var(--mono);font-size:13px;color:var(--ink)}
.zclose{align-self:flex-end;font:inherit;font-size:14px;padding:6px 14px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
</style>

<div class="wrap">
  <header>
    <div class="eyebrow">__EYEBROW__</div>
    <h1>__TITLE__</h1>
    <p class="sub">Frames per second on the phone, __UNIT__ by __UNIT__, build by build. Target: 60 fps with no dropped frames during gameplay.</p>
    <p class="sub" id="prov">__PROV__</p>
  </header>

  <section class="card" aria-labelledby="h-final">
    <h2 id="h-final">fps by __UNIT__ and quality level</h2>
    <p class="sub">__FPSINTRO__</p>
    <div class="tiles" id="ftiles" style="margin-top:14px"></div>
    <div class="ctl">
      <label class="pick"><span class="eyebrow">Song section</span><select id="secpick" aria-label="Song section"></select></label>
      <label class="chk"><input type="checkbox" id="stresspick"><span>__STRESSLABEL__</span></label>
    </div>
    <div class="lgd" id="tlegend"></div>
    <div id="lvchart"></div>
    <p class="desc" id="lvnote"></p>
  </section>

  <section class="card" aria-labelledby="h-shots">
    <h2 id="h-shots">Gameplay screenshots, every __UNIT__</h2>
    <p class="sub">__SHOTSINTRO__</p>
    <div class="shotrow" id="shotrow" role="list" aria-label="Gameplay screenshots, scroll sideways"></div>
    <p class="desc">Scroll sideways; tap a screenshot to zoom in.</p>
    <div class="zoom" id="zoom" hidden role="dialog" aria-modal="true" aria-label="Screenshot, zoomed">
      <button type="button" class="zclose" id="zclose" aria-label="Close">Close</button>
      <img id="zimg" alt="">
      <div class="zcap" id="zcap"></div>
    </div>
  </section>

  <section class="card" aria-labelledby="h-feat">
    <h2 id="h-feat">What each switch costs, every __UNIT__</h2>
    <p class="sub">GPU time per frame on the phone, one switch off against on (a reading is good to about 0.5 ms). One column per __UNIT__, stacked by switch, with the sum on top (the switches are measured one at a time, so the sum is an estimate). __COSTINTRO__</p>
    <div class="lgd" id="costlegend"></div>
    <div id="costchart"></div>
    <p class="desc" id="fnote"></p>
  </section>

  <details class="card hist">
    <summary><h2 id="h-build">Every __UNIT__, one build at a time</h2></summary>
    <p class="sub">Pick a build to see where each __UNIT__ stood. The black tick is the previous build.</p>
    <div style="display:flex;flex-direction:column;gap:10px;margin-top:14px">
      <div class="seg" id="builds" role="group" aria-label="Build"></div>
      <div class="seg" id="modes" role="group" aria-label="Song section"></div>
    </div>
    <p class="desc" id="desc"></p>
    <div class="tiles" id="tiles" style="margin-top:16px"></div>
    <div id="bars" style="margin-top:14px"></div>
    <div class="legend">
      <span><i style="background:var(--good)"></i>57 fps or more</span>
      <span><i style="background:var(--warn)"></i>50 to 57</span>
      <span><i style="background:var(--bad)"></i>under 50</span>
      <span><i style="background:var(--muted)"></i>dashed line = 60 fps</span>
    </div>
  </details>

  <details class="card hist">
    <summary><h2 id="h-trend">Change over the builds</h2></summary>
    <p class="sub">Each __UNIT__'s fps at every build for the chosen song section. The ring marks the build selected above.</p>
    <div class="small" id="small"></div>
  </details>

  <section class="card" aria-labelledby="h-eff">
    <h2 id="h-eff">What each optimization did</h2>
    <p class="sub">GPU time is per frame. Interleaved A/B means the change was switched on and off several times in one run, so heat drift cancels out.</p>
    <div class="tw" style="margin-top:12px"><table>
      <thead><tr><th>Change</th><th>Kind</th><th>Measured effect</th><th>Result</th></tr></thead>
      <tbody id="eff"></tbody>
    </table></div>
  </section>



  <section class="card" aria-labelledby="h-dev">
    <h2 id="h-dev">Device tiers</h2>
    <p class="sub">Worst fps over all __UNITS_PL__ and song sections, and the frames over 33 ms, per quality level. Only phones that were measured fill a cell: a tier without a measured phone says so, nothing is estimated.</p>
    __DEVMATRIX__
  </section>

  <section class="card" aria-labelledby="h-next">
    <h2 id="h-next">Where it stands</h2>
    __STATUS__
  </section>
</div>

<script>
// fps per theme as [Normal, Climax]; d = null while a build is still being measured
const THEMES=__UNITS__;
const BUILDS=__BUILDS__;
const MODES=["Normal","Climax"];
let cur=BUILDS.length-1, mode=0;
const MEDIUM_LATEST=true;
const $=id=>document.getElementById(id);
const col=f=>f>=57?"var(--good)":f>=50?"var(--warn)":"var(--bad)";
const fmt=v=>v.toFixed(1);

function seg(el,items,sel,on){
  el.innerHTML="";
  items.forEach((t,i)=>{const b=document.createElement("button");b.type="button";b.textContent=t.label||t;
    b.setAttribute("aria-pressed",i===sel);if(t.off){b.disabled=true;b.style.opacity=.5}
    b.addEventListener("click",()=>on(i));el.appendChild(b)});
}
function val(b,t){return BUILDS[b].d?BUILDS[b].d[t][mode]:null}

function render(){
  seg($("builds"),BUILDS.map((b,i)=>({label:(i+1)+" · "+b.id+(b.d?"":" (measuring)"),off:!b.d})),cur,i=>{cur=i;render()});
  seg($("modes"),MODES,mode,i=>{mode=i;render()});
  $("desc").textContent=BUILDS[cur].desc;
  const prev=cur>0&&BUILDS[cur-1].d?cur-1:null;
  const vals=THEMES.map((_,t)=>val(cur,t));
  const at60=vals.filter(v=>v>=57).length, worst=Math.min(...vals), avg=vals.reduce((a,b)=>a+b,0)/vals.length;
  $("tiles").innerHTML=
   `<div class="tile"><b>${at60} of ${THEMES.length}</b><span>__UNITS_PL__ at 57 fps or more</span></div>`+
   `<div class="tile"><b class="mono" style="color:${col(worst)}">${fmt(worst)}</b><span>worst __UNIT__, fps</span></div>`+
   `<div class="tile"><b class="mono">${fmt(avg)}</b><span>average of all __UNITS_PL__, fps</span></div>`;
  const order=THEMES.map((n,i)=>i).sort((a,b)=>vals[a]-vals[b]);
  const lo=30,hi=62,pos=v=>Math.max(0,Math.min(100,(v-lo)/(hi-lo)*100));
  $("bars").innerHTML=order.map(t=>{
    const v=vals[t], p=prev!==null?val(prev,t):null, dlt=p===null?null:v-p;
    const cls=dlt===null?"flat":dlt>0.4?"up":dlt<-0.4?"down":"flat";
    return `<div class="row"><span class="name">${THEMES[t]}</span>
      <div class="track" role="img" aria-label="${THEMES[t]} ${fmt(v)} fps">
        <div class="bar" style="width:${pos(v)}%;background:${col(v)}"></div>
        ${p!==null?`<div class="ghost" style="left:calc(${pos(p)}% - 1px)"></div>`:""}
        <div class="tgt" style="left:${pos(60)}%"></div></div>
      <span class="val">${fmt(v)} <span class="${cls}">${dlt===null?"":(dlt>0?"+":"")+fmt(dlt)}</span></span></div>`}).join("");
  const W=200,H=70,pad=6,n=BUILDS.length, x=i=>pad+i*(W-2*pad)/(n-1), y=v=>H-pad-(Math.max(36,Math.min(61,v))-36)/25*(H-2*pad);
  $("small").innerHTML=THEMES.map((name,t)=>{
    const pts=BUILDS.map((b,i)=>b.d?[x(i),y(b.d[t][mode]),b.d[t][mode]]:null);
    const done=pts.filter(Boolean);
    const line=done.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" ");
    const last=done[done.length-1], sel=pts[cur];
    return `<div class="sm"><header><b>${name}</b><span class="mono" style="color:${col(last[2])}">${fmt(last[2])}</span></header>
     <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${name} fps over builds">
      <line x1="${pad}" x2="${W-pad}" y1="${y(60).toFixed(1)}" y2="${y(60).toFixed(1)}" stroke="var(--muted)" stroke-dasharray="4 4" stroke-width="1"/>
      <polyline points="${line}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      ${done.map(p=>`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3" fill="${col(p[2])}"/>`).join("")}
      ${sel?`<circle cx="${sel[0].toFixed(1)}" cy="${sel[1].toFixed(1)}" r="6.5" fill="none" stroke="var(--ink)" stroke-width="1.5"/>`:""}
     </svg></div>`}).join("");
}

const EFF=__EFF__;
const RES={kept:"Kept",no:"No gain",try:"Measured"};
$("eff").innerHTML=EFF.map(e=>`<tr><td>${e[0]}</td><td><span class="pill">${e[1]}</span></td><td>${e[2]}</td><td><span class="pill ${e[3]}">${RES[e[3]]}</span></td></tr>`).join("");

/* Final grid. FINAL[theme][level] = fps and frames over 33 ms for [Start, Normal, Rising, Climax], 5 s each. */
const FINAL=__FINAL__;
const FEATCOST=__FEATCOST__;
const STRESS=__STRESS__;
const FMODES=__SECTIONLABELS__, LEVELS=__LEVELS__;
const fcol=f=>f>=59?"var(--good)":f>=55?"var(--warn)":"var(--bad)";
const onoff=(on)=>on?'<span class="on">on</span>':'<span class="off">off</span>';
(function(){
  const names=Object.keys(FINAL);
  const worst=l=>Math.min(...names.map(n=>Math.min(...FINAL[n][l].map(x=>x[0]))));
  const slow=l=>names.reduce((a,n)=>a+FINAL[n][l].reduce((s,x)=>s+x[1],0),0);
  $("ftiles").innerHTML=LEVELS.map(l=>`<div class="tile"><b class="mono" style="color:${fcol(worst(l))}">${worst(l).toFixed(1)}</b><span>${l[0].toUpperCase()+l.slice(1)}: worst cell, fps · ${slow(l)} slow frames in 32 cells</span></div>`).join("");
  const LVN=["Low","Medium","High"];
  const secpick=$("secpick"), stresspick=$("stresspick");
  secpick.innerHTML=FMODES.map((m,i)=>`<option value="${i}">${m}</option>`).join("");
  const LC=["var(--lv1)","var(--lv2)","var(--lv3)"];
  $("tlegend").innerHTML=LVN.map((l,k)=>`<span><i style="background:${LC[k]}"></i>${l}</span>`).join("")+`<span><i style="background:var(--bad)"></i>red number = frames over 33 ms</span><span>dashed line = 60 fps</span>`;
  function draw(){
    const i=+secpick.value, st=stresspick.checked, src=st?STRESS:FINAL;
    const W=720,H=320,L=34,R=8,T=20,B=52, lo=30, gw=(W-L-R)/names.length, bw=Math.min(22,(gw-10)/3);
    const y=f=>T+(H-T-B)*(1-(Math.max(lo,Math.min(60,f))-lo)/(60-lo));
    let g=`<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="fps per theme, one bar per quality level">`;
    for(let f=lo;f<=60;f+=5) g+=`<line x1="${L}" x2="${W-R}" y1="${y(f)}" y2="${y(f)}" stroke="var(--line)"/><text x="${L-6}" y="${y(f)+4}" text-anchor="end">${f}</text>`;
    g+=`<line x1="${L}" x2="${W-R}" y1="${y(60)}" y2="${y(60)}" stroke="var(--muted)" stroke-dasharray="5 4"/>`;
    names.forEach((n,t)=>{
      const gx=L+gw*t+(gw-(bw*3+4))/2;
      if(!src[n]){g+=`<text x="${gx+(bw*3+4)/2}" y="${y(lo)-8}" text-anchor="middle">n/a</text>`}
      else LEVELS.forEach((l,k)=>{
        const c=src[n][l][i], x=gx+k*(bw+2), top=y(c[0]);
        g+=`<g><title>${n}, ${LVN[k]}, ${FMODES[i]}${st?__STRESSTAG__:""}: ${c[0].toFixed(1)} fps, ${c[1]} frames over 33 ms</title><rect x="${x.toFixed(1)}" y="${top.toFixed(1)}" width="${bw}" height="${(y(lo)-top).toFixed(1)}" rx="2" fill="${LC[k]}"/></g>`;
        if(c[0]<57) g+=`<text class="v" x="${(x+bw/2).toFixed(1)}" y="${(top-4).toFixed(1)}" text-anchor="middle" style="font-size:10px">${c[0].toFixed(0)}</text>`;
        if(c[1]>0) g+=`<text class="slow" x="${(x+bw/2).toFixed(1)}" y="${H-B+13}" text-anchor="middle" style="font-size:10px">${c[1]}</text>`;
      });
      g+=`<text x="${gx+(bw*3+4)/2}" y="${H-10}" text-anchor="middle" style="fill:var(--ink);font-size:12px">${n}</text>`;
    });
    $("lvchart").innerHTML=g+`</svg>`;
    const miss=names.filter(n=>!src[n]);
    $("lvnote").textContent=(st&&miss.length?`Not measured under the stress scale: ${miss.join(", ")}. `:"")+`The axis shows 30 to 60 fps; the dashed line is 60 fps; bars under 57 fps carry their value. ${st?__SCALESTRESS__:__SCALEREL__}`;
  }
  secpick.addEventListener("change",draw); stresspick.addEventListener("change",draw); draw();
  const SHOTS=__SHOTS__, SHOTALT=__SHOTALT__, SHOTCAP=__SHOTCAP__;
  const zoom=$("zoom");
  $("shotrow").innerHTML=names.map(n=>`<button type="button" class="shotitem" role="listitem" data-n="${n}" aria-label="${n}, zoom in"><img src="${SHOTS[n]}" alt="${n}${SHOTALT}" loading="lazy"><span>${n}</span></button>`).join("");
  function openZoom(n){$("zimg").src=SHOTS[n];$("zimg").alt=n+SHOTALT;$("zcap").textContent=n+SHOTCAP;zoom.hidden=false;$("zclose").focus()}
  function closeZoom(){zoom.hidden=true;$("zimg").removeAttribute("src")}
  $("shotrow").addEventListener("click",e=>{const b=e.target.closest(".shotitem");if(b)openZoom(b.dataset.n)});
  zoom.addEventListener("click",closeZoom);
  document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!zoom.hidden)closeZoom()});
  // GPU cost of each switch, every theme
  const SW=[...new Set(names.flatMap(n=>Object.keys(FEATCOST[n]||{})))];
  const SC=["#c0702f","#7c9fb8","#8cb83b","#b07aa1","#d4a017","#e15759","#76b7b2","#59a14f","#4e79a7","#9c755f"];
  $("costlegend").innerHTML=SW.map((s,k)=>`<span><i style="background:${SC[k%SC.length]}"></i>${s}</span>`).join("");
  (function(){
    const tot=n=>SW.reduce((a,s)=>a+((FEATCOST[n]||{})[s]||0),0);
    const W=720,H=320,L=40,R=8,T=22,B=40, mx=Math.max(2,Math.ceil(Math.max(...names.map(tot))+0.5));
    const gw=(W-L-R)/names.length, bw=Math.min(54,gw-16), y=v=>T+(H-T-B)*(1-v/mx);
    let g=`<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="GPU ms per theme, stacked by switch">`;
    for(let v=0;v<=mx;v+=0.5) g+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end">${v.toFixed(1)}</text>`;
    g+=`<text x="4" y="12">ms</text>`;
    names.forEach((n,t)=>{
      const x=L+gw*t+(gw-bw)/2; let acc=0;
      SW.forEach((s,k)=>{
        const v=(FEATCOST[n]||{})[s]; if(!v) return;
        const top=y(acc+v), h=y(acc)-top; acc+=v;
        g+=`<g><title>${n}: ${s}, ~${v.toFixed(1)} ms</title><rect x="${x.toFixed(1)}" y="${top.toFixed(1)}" width="${bw}" height="${Math.max(1,h-1).toFixed(1)}" rx="2" fill="${SC[k%SC.length]}"/></g>`;
        if(h>=16) g+=`<text x="${(x+bw/2).toFixed(1)}" y="${(top+h/2+4).toFixed(1)}" text-anchor="middle" style="font-size:10px;fill:#fff">${v.toFixed(1)}</text>`;
      });
      g+=`<text class="v" x="${(x+bw/2).toFixed(1)}" y="${(y(acc)-5).toFixed(1)}" text-anchor="middle" style="font-weight:600">${acc.toFixed(1)}</text>`;
      g+=`<text x="${(x+bw/2).toFixed(1)}" y="${H-12}" text-anchor="middle" style="fill:var(--ink);font-size:12px">${n}</text>`;
    });
    $("costchart").innerHTML=g+`</svg>`;
  })();
  $("fnote").textContent=__COSTNOTE__;
})();

render();
</script>
