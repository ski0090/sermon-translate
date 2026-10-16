// 프로젝트 작업 화면: 왼쪽 영상, 오른쪽 단계 패널(자막 읽기 · 정리와 검수 · 음성 · 내보내기), 아래 타임라인(잘라내기 구간).
// 단계 패널은 work-*.js에 있고, 화면 전체가 함께 쓰는 상태와 동작(W)을 provide로 넘긴다. 위쪽 줄의 단계 버튼은 header로 옮겨 그린다
import {computed,inject,nextTick,onMounted,onUnmounted,provide,reactive,ref,watch} from "./vendor/vue.esm-browser.prod.js";
import {api,store,fmt,jobMsg,openOld} from "./lib.js";
import ScanPanel from "./work-scan.js";
import ReviewPanel from "./work-review.js";
import TtsPanel from "./work-tts.js";

const STEPS=[["scan","자막 읽기"],["review","정리와 검수"],["tts","음성"],["export","내보내기"]];
const ORDER=["load","scan","review","tts","export"];

// 아직 새 화면에 옮기지 않은 단계
const OldPanel={
  setup(){return {W:inject("W")};},
  template:`<div class="card">이 단계는 아직 새 화면에 없습니다. <button class="small" @click="W.openOld()">지금 화면에서 열기</button></div>`,
};

const SettingsModal={
  emits:["close"],
  setup(_,{emit}){
    const W=inject("W"),s=W.d.settings;
    const f=reactive({tool:s.tool,per_strip:s.per_strip,workers:s.workers,min_gap:s.min_gap,ai_tidy:!!s.ai_tidy,tts_steps:String(s.tts_steps||8),
      dict:Object.entries(s.dictionary||{}).map(([k,v])=>k+"="+v).join("\n")});
    async function save(){
      const dictionary={};f.dict.split("\n").forEach(l=>{const i=l.indexOf("=");if(i>0)dictionary[l.slice(0,i).trim()]=l.slice(i+1).trim();});
      const body={tool:f.tool,per_strip:+f.per_strip,workers:+f.workers,min_gap:+f.min_gap,ai_tidy:f.ai_tidy,dictionary};
      if(String(s.tts_steps||8)!==f.tts_steps){if(!confirm("음성 합성 품질을 바꾸면 모든 문장의 음성을 다시 만듭니다. 계속할까요?"))return;body.tts_steps=+f.tts_steps;}
      try{await api(W.P("/settings"),"POST",body);}catch(e){return alert(e.message);}
      emit("close");await W.reload();
    }
    return {f,save};
  },
  template:`<div class="modal"><div class="card">
    <h2 style="margin-top:0">프로젝트 설정</h2>
    <label>AI 도구</label>
    <select v-model="f.tool"><option value="claude">claude</option><option value="codex">codex</option></select>
    <label>한 묶음에 넣는 자막 수 (20~30)</label><input v-model="f.per_strip" type="number" min="5" max="40">
    <label>동시에 읽는 묶음 수</label><input v-model="f.workers" type="number" min="1" max="8">
    <label>자막 없음 기준 시간(초)</label><input v-model="f.min_gap" type="number" min="5" max="120">
    <label><input v-model="f.ai_tidy" type="checkbox"> 자막 읽기 뒤 AI가 문장 정리 (문장 묶기, 글자 교정, 읽는 글, 확인 필요 표시)</label>
    <label>음성 합성 품질</label>
    <select v-model="f.tts_steps"><option value="8">표준 (문장당 약 5초)</option><option value="4">빠름 (품질 조금 낮음, 약 2배 빠름)</option></select>
    <div class="muted">품질을 바꾸면 모든 문장의 음성을 다시 만듭니다.</div>
    <label>읽기 사전 (한 줄에 하나, 보이는 글=읽는 글)</label>
    <textarea v-model="f.dict" rows="6" placeholder="할렐루야=할렐루우야" style="width:100%"></textarea>
    <div class="row" style="justify-content:flex-end;margin-top:12px"><button @click="$emit('close')">닫기</button><button class="primary" @click="save">저장</button></div>
  </div></div>`,
};

export default {
  props:["pid"],
  components:{ScanPanel,ReviewPanel,TtsPanel,OldPanel,SettingsModal},
  setup(props){
    const video=ref(null),audio=ref(null),canvas=ref(null);
    const W=reactive({pid:props.pid,d:null,plan:[],step:"scan",filter:"all",preview:false,cur:0,cursent:null,sel:null,err:null,exportFiles:null,settings:false,
      P:path=>`/api/p/${encodeURIComponent(props.pid)}${path}`});
    provide("W",W);
    let first=0,poll=null,polling=false,userScrolling=false,scrollTimer=null;

    async function reload(){
      const d=await api(W.P(""));
      W.plan=d.sentences.some(s=>s.tts)?await api(W.P("/plan")):[];
      W.d=d;W.err=null;store.workName=d.name;
    }
    function stopPoll(){clearInterval(poll);poll=null;}
    function startPoll(){
      stopPoll();
      poll=setInterval(async()=>{
        if(polling)return;polling=true;
        try{const j=await api(W.P("/job"));if(!W.d)return;W.d.job=j;
          if(!j||j.done){stopPoll();await reload();if(j)onJobDone(j);}}  // 대기열에서 뺀 경우(j 없음)도 멈춘다
        catch(e){}finally{polling=false;}
      },1000);
    }
    function onJobDone(j){
      if(j.error||j.cancelled)return;
      if(j.kind==="read")W.step="review";
      else if(j.kind==="export"){W.step="export";W.exportFiles=j.result&&j.result.files;}
    }
    Object.assign(W,{
      reload,
      async startJob(kind,params={}){
        try{await api(W.P("/job"),"POST",{kind,...params});}catch(e){W.err=e.message;return;}
        await reload();startPoll();
      },
      seek(t){const v=video.value;v.currentTime=t;v.play().catch(()=>{});},
      videoTime:()=>video.value?video.value.currentTime:0,
      play(src){const a=audio.value;a.src=src;a.play().catch(()=>{});return a;},
      openOld:()=>openOld("?p="+encodeURIComponent(props.pid)),
      go(step){W.step=step;W.preview=false;if(video.value)video.value.muted=false;if(step==="tts"&&W.filter==="ai")W.filter="all";},
      setPreview(on){W.preview=on;video.value.muted=on;if(!on)audio.value.pause();},
    });

    const job=computed(()=>W.d&&W.d.job);
    const jobOn=computed(()=>job.value&&!job.value.done&&!job.value.error);
    const errText=computed(()=>W.err||(job.value&&job.value.error?"작업 실패: "+job.value.error:""));
    const steps=computed(()=>{const d=W.d;if(!d)return [];const furthest=ORDER.indexOf(d.step);
      return STEPS.map(([k,n],i)=>{const idx=i+1;
        return {k,n,idx,done:idx<=furthest,avail:idx<=Math.max(furthest,1)||(k==="review"&&d.sentences.length)||(k==="tts"&&d.sentences.length)||(k==="export"&&d.sentences.some(s=>s.tts))};});});
    const panel=computed(()=>({scan:"ScanPanel",review:"ReviewPanel",tts:"TtsPanel"})[W.step]||"OldPanel");

    /* ----- 영상 ----- */
    function onMeta(){if(video.value.currentTime<0.1)video.value.currentTime=first;}
    function onTime(){
      const v=video.value,t=v.currentTime;W.cur=t;if(!W.d)return;
      // 미리 듣기 중에는 잘라내기 구간을 건너뛴다
      const cut=W.d.cuts.find(c=>t>=c.start&&t<c.end-0.05);if(cut&&W.preview){v.currentTime=cut.end;return;}
      const s=W.d.sentences.find(x=>t>=x.start&&t<x.end);
      if(s&&W.cursent!==s.id){
        W.cursent=s.id;
        if(W.filter!=="over"&&!userScrolling)nextTick(()=>{const el=document.getElementById("s"+s.id);if(el)el.scrollIntoView({block:"nearest"});});
        if(W.preview&&s.tts){const a=audio.value;a.src=W.P("/tts/"+s.tts);a.playbackRate=1;a.play().catch(()=>{});}
      }
    }
    const onWheel=()=>{userScrolling=true;clearTimeout(scrollTimer);scrollTimer=setTimeout(()=>{userScrolling=false;},4000);};
    const onKey=e=>{if(e.code==="Space"&&video.value&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)){e.preventDefault();video.value.paused?video.value.play():video.value.pause();}};

    /* ----- 타임라인 ----- */
    function draw(){
      const tl=canvas.value;if(!tl||!W.d)return;
      const dpr=devicePixelRatio,Wd=tl.clientWidth||800,H=84;if(tl.width!==Wd*dpr){tl.width=Wd*dpr;tl.height=H*dpr;}
      const ctx=tl.getContext("2d");ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,Wd,H);
      const d=W.d,D=d.info.duration,x=t=>t/D*Wd;
      ctx.fillStyle="#eceef2";ctx.fillRect(0,0,Wd,H);
      d.ranges.gaps.forEach(g=>{ctx.fillStyle="#c3c8d0";ctx.fillRect(x(g.start),0,Math.max(1,x(g.end)-x(g.start)),H);});
      d.ranges.lyrics.forEach(g=>{ctx.fillStyle="rgba(228,180,0,.55)";ctx.fillRect(x(g.start),0,Math.max(1,x(g.end)-x(g.start)),H);});
      d.sentences.forEach(s=>{ctx.fillStyle=s.tts?"#5b8def":"#9db6f2";ctx.fillRect(x(s.start),26,Math.max(1,x(s.end)-x(s.start)-0.5),32);});
      const pm=Object.fromEntries(W.plan.map(p=>[p.sid,p]));
      d.sentences.forEach(s=>{const p=pm[s.id];if(p&&(p.overflow||p.fixed_overflow)){ctx.fillStyle=p.fixed_overflow?"#b91c1c":"#f59e0b";ctx.fillRect(x(s.start),22,Math.max(2,x(s.end)-x(s.start)),3);}});
      d.cuts.forEach(c=>{ctx.fillStyle="rgba(214,69,93,.45)";ctx.fillRect(x(c.start),0,Math.max(1,x(c.end)-x(c.start)),H);ctx.strokeStyle="#d6455d";ctx.strokeRect(x(c.start)+.5,.5,Math.max(1,x(c.end)-x(c.start))-1,H-1);});
      if(W.sel){ctx.fillStyle="rgba(245,158,11,.35)";ctx.fillRect(x(W.sel[0]),0,Math.max(1,x(W.sel[1])-x(W.sel[0])),H);}
      ctx.fillStyle="#6b7280";ctx.font="11px sans-serif";for(let m=0;m<D;m+=300){ctx.fillRect(x(m),H-14,1,14);ctx.fillText(fmt(m),x(m)+3,H-3);}
      ctx.fillStyle="#111";ctx.fillRect(x(W.cur||0)-1,0,2,H);
    }
    watch(()=>[W.d,W.plan,W.sel,W.cur],draw,{flush:"post"});
    let dragStart=null,dragMoved=false;
    function tlDown(e){dragStart=e.offsetX;dragMoved=false;}
    function tlMove(e){
      if(dragStart===null||!W.d)return;const D=W.d.info.duration,Wd=canvas.value.clientWidth;
      if(Math.abs(e.offsetX-dragStart)>3)dragMoved=true;if(!dragMoved)return;
      const a=Math.min(dragStart,e.offsetX)/Wd*D,b=Math.max(dragStart,e.offsetX)/Wd*D;W.sel=[Math.max(0,a),Math.min(D,b)];
    }
    function tlUp(){
      if(dragStart===null||!W.d)return;const D=W.d.info.duration,Wd=canvas.value.clientWidth;
      if(!dragMoved){W.sel=null;W.seek(dragStart/Wd*D);}dragStart=null;
    }
    const selInfo=computed(()=>W.sel?`선택: ${fmt(W.sel[0])} – ${fmt(W.sel[1])} (${Math.round(W.sel[1]-W.sel[0])}초)`:"타임라인을 끌어서 구간을 선택하세요.");
    async function setCuts(cuts){try{await api(W.P("/cuts"),"POST",{cuts});}catch(e){alert(e.message);}await reload();}
    function cutSel(){if(!W.sel)return;const cuts=W.d.cuts.concat([{start:W.sel[0],end:W.sel[1],label:"잘라내기"}]);W.sel=null;setCuts(cuts);}
    function cutCands(){
      const d=W.d,cands=d.ranges.gaps.map(g=>({...g,label:"자막 없음"})).concat(d.ranges.lyrics.map(g=>({...g,label:"찬양"})));
      if(!cands.length)return alert("잘라낼 후보 구간이 없습니다.");
      if(!confirm(`자막 없음 ${d.ranges.gaps.length}개, 찬양 후보 ${d.ranges.lyrics.length}개 구간을 잘라내기로 지정할까요?`))return;
      setCuts(d.cuts.concat(cands));
    }
    function uncut(i){const cuts=W.d.cuts.slice();cuts.splice(i,1);setCuts(cuts);}

    onMounted(async()=>{
      addEventListener("keydown",onKey);addEventListener("mouseup",tlUp);addEventListener("resize",draw);
      try{await reload();}catch(e){W.err=e.message;return;}
      const d=W.d;
      // 문장이 있으면 정리와 검수부터 연다(서버는 review 단계를 따로 적지 않는다)
      W.step=!d.step||d.step==="load"?"scan":d.step==="scan"&&d.sentences.length?"review":d.step;
      first=(d.sentences[0]||d.captions[0]||{}).start||0;W.cur=first;
      if(d.job&&d.job.running)startPoll();
    });
    onUnmounted(()=>{stopPoll();removeEventListener("keydown",onKey);removeEventListener("mouseup",tlUp);removeEventListener("resize",draw);store.workName=null;});
    return {W,video,audio,canvas,job,jobOn,errText,steps,panel,onMeta,onTime,onWheel,tlDown,tlMove,selInfo,cutSel,cutCands,uncut,fmt,jobMsg,
      cancel:()=>api(W.P("/job/cancel"),"POST",{})};
  },
  template:`<div v-if="!W.d" class="start"><div v-if="W.err" class="err">{{W.err}}</div><div v-else class="card muted">불러오는 중…</div></div>
  <section v-else class="work">
    <Teleport defer to="#hdrSlot">
      <nav class="steps"><button v-for="s in steps" :key="s.k" :class="{active:s.k===W.step,done:s.done}" :disabled="!s.avail" @click="W.go(s.k)">{{s.idx}}. {{s.n}}</button></nav>
      <button class="small" @click="W.settings=true">프로젝트 설정</button>
    </Teleport>
    <div class="wleft">
      <video ref="video" controls preload="metadata" :src="W.P('/video')" @loadedmetadata="onMeta" @timeupdate="onTime"></video>
      <div class="row"><span class="time">{{fmt(W.cur)}} / {{fmt(W.d.info.duration)}}</span><span class="muted">문장을 누르면 그 시점으로 이동합니다. <kbd>Space</kbd> 재생/멈춤</span></div>
    </div>
    <div class="wright" @wheel.passive="onWheel">
      <div v-if="jobOn" class="job"><span>{{jobMsg(job)}}</span><div class="bar"><i :style="{width:Math.round(job.progress*100)+'%'}"></i></div><span class="time">{{Math.round(job.progress*100)}}%</span><button class="small" @click="cancel">중단</button></div>
      <div v-if="errText" class="err">{{errText}}</div>
      <div class="panel"><component :is="panel"/></div>
    </div>
    <div class="wbottom">
      <canvas ref="canvas" class="timeline" @mousedown="tlDown" @mousemove="tlMove"></canvas>
      <div class="tlbar">
        <span class="legend"><span><i style="background:#5b8def"></i>문장</span><span><i style="background:var(--cut)"></i>잘라내기</span><span><i style="background:var(--gap)"></i>자막 없음</span><span><i style="background:var(--lyric)"></i>찬양 후보</span><span><i style="background:#f59e0b"></i>선택</span></span>
        <span class="muted">{{selInfo}}</span>
        <button class="small" :disabled="!W.sel" @click="cutSel">선택 구간 잘라내기</button>
        <button class="small" @click="cutCands">자막 없음 · 찬양 후보 모두 잘라내기</button>
        <span><span v-for="(c,i) in W.d.cuts" :key="i+':'+c.start" class="badge" style="margin-left:6px">{{c.label||"잘라내기"}} {{fmt(c.start)}}–{{fmt(c.end)}} <a style="cursor:pointer;color:var(--bad)" @click="uncut(i)">✕</a></span></span>
      </div>
    </div>
    <audio ref="audio"></audio>
    <SettingsModal v-if="W.settings" @close="W.settings=false"/>
  </section>`,
};
