// 설정 > AI 도구 화면: Claude, Codex, Antigravity마다 설치·로그인·플랜, 사용 켜기/끄기, 모델 고르기, 지금 쓰는 모델,
// 로그인·로그아웃·연결 시험. Codex 로그인 중에만 2초마다 새로 읽고, 고르는 중인 모델 칸은 덮지 않는다
import {computed,onMounted,onUnmounted,ref,watch} from "./vendor/vue.esm-browser.prod.js";
import {api,every,when,TOOLS} from "./lib.js";

const ToolCard={
  props:["x"],emits:["reload"],
  setup(props,{emit}){
    const sel=ref(props.x.model||""),text=ref(""),testing=ref(false);
    watch(()=>props.x.model,v=>{sel.value=v||"";});
    // 목록에 없는 모델을 직접 골라 두었으면 그것도 보인다
    const opts=computed(()=>{const ms=props.x.models||[],m=props.x.model;
      return ms.map(([v,l])=>({v,t:l+(v&&v!==l?" ("+v+")":"")})).concat(m&&!ms.some(([v])=>v===m)?[{v:m,t:m}]:[]);});
    const lg=computed(()=>props.x.login);
    async function call(path,body,fresh){try{await api(path,"POST",body);}catch(e){alert(e.message);}emit("reload",fresh);}
    const t=()=>props.x.tool;
    return {sel,text,testing,opts,lg,when,
      setEnabled:on=>call("/api/tools",{tool:t(),enabled:on}),
      saveModel(){const model=text.value.trim()||sel.value;text.value="";document.activeElement.blur();call("/api/tools",{tool:t(),model});},
      async test(){testing.value=true;await call(`/api/tools/${t()}/test`,{},true);testing.value=false;},
      login(){if(props.x.logged_in&&!confirm("새로 로그인을 시작하면 지금 로그인이 잠시 풀립니다. 새 로그인을 끝내지 않으면(취소, 15분 지남) 지금 로그인을 되살립니다. 시작할까요?"))return;
        call(`/api/tools/${t()}/login`,{});},
      cancel:()=>call(`/api/tools/${t()}/cancel`,{},true),
      logout(){if(confirm("로그아웃하면 다시 로그인할 때까지 이 도구를 쓸 수 없습니다. 로그아웃할까요?"))call(`/api/tools/${t()}/logout`,{},true);},
    };
  },
  template:`<div class="card" style="margin-bottom:12px">
    <div class="row" style="justify-content:space-between;margin:0"><strong style="font-size:15px">{{x.name}}</strong>
      <label class="row" style="margin:0"><input type="checkbox" :checked="x.enabled" :disabled="!x.installed" @change="setEnabled($event.target.checked)"> 사용</label></div>
    <template v-if="!x.installed">
      <div class="row"><span class="badge warn">설치 안 됨</span></div>
      <div class="muted">서버 PC 터미널에서 설치합니다:</div><pre class="tlcode">{{x.install}}</pre>
      <div class="muted">설치한 뒤 로그인: {{x.login_help}} 그다음 "상태 다시 읽기"를 누르세요.</div>
    </template>
    <template v-else>
      <div class="row">
        <span v-if="x.logged_in===true" class="badge ok">로그인됨</span><span v-else-if="x.logged_in===false" class="badge bad">로그인 안 됨</span><span v-else class="badge">로그인 확인 전</span>
        <span v-if="x.plan" class="badge ok">플랜 {{x.plan}}</span><span v-if="x.account" class="muted">{{x.account}}</span>
        <span class="muted">{{x.version||""}}</span>
      </div>
      <div class="row">지금 쓰는 모델: <b>{{x.active_model||"도구 기본"}}</b><span v-if="x.model" class="badge">직접 고름</span>
        <span class="muted">· 마지막 호출: <template v-if="x.seen_model">{{x.seen_model}}{{x.seen_t?" ("+when(x.seen_t)+" 호출 기준)":""}}</template><template v-else>아직 호출 기록 없음</template></span></div>
      <div class="row">모델 <select v-model="sel"><option v-for="o in opts" :key="o.v" :value="o.v">{{o.t}}</option></select>
        <input v-if="x.tool!=='claude'" v-model="text" placeholder="목록에 없으면 이름 입력" style="width:200px"><button class="small" @click="saveModel">모델 저장</button></div>
      <div v-if="x.tool==='claude'" class="muted">사용량을 다 쓰면 Fable로 이어 하기: <b>{{x.fallback?"켜짐":"꺼짐"}}</b><span v-if="x.fallback_now" class="badge ok">지금 Fable로 작업 중</span> (설정 &gt; 스케줄에서 바꿈)</div>
      <div v-if="x.logged_in===false" class="muted">로그인: {{x.login_help}}</div>
      <div v-if="x.tool==='claude'" class="muted">Claude 로그아웃은 이 PC의 Claude Code도 같이 로그아웃되어 화면에서는 하지 않습니다. 쓰지 않으려면 "사용"을 끄세요.</div>
      <div v-if="lg&&(lg.running||lg.error||lg.ok)" class="tllogin">
        <template v-if="lg.running"><b>로그인 진행 중</b> — 아래 주소를 아무 기기의 브라우저에서 열고 코드를 넣으세요.<br>
          <a v-if="lg.url" :href="lg.url" target="_blank">{{lg.url}}</a><template v-else>주소를 기다리는 중…</template><template v-if="lg.code"> · 코드 <b style="font-size:16px;letter-spacing:1px">{{lg.code}}</b></template></template>
        <span v-else-if="lg.ok" class="badge ok">로그인했습니다</span>
        <template v-else><span class="badge bad">로그인 실패</span> {{lg.error||""}}</template>
        <pre v-if="lg.lines&&lg.lines.length&&!lg.url" class="tlcode">{{lg.lines.join("\\n")}}</pre>
        <button v-if="lg.running" class="small" @click="cancel">로그인 취소</button>
      </div>
      <div class="row">
        <button class="small" :disabled="testing" @click="test">{{testing?"시험 중…":"연결 시험"}}</button>
        <button v-if="x.can_login&&!x.logged_in" class="small primary" @click="login">로그인</button>
        <button v-if="x.can_login&&x.logged_in" class="small" @click="login">다른 계정으로 로그인</button>
        <button v-if="x.can_logout&&x.logged_in!==false" class="small" @click="logout">로그아웃 (설정 해제)</button>
        <span v-if="x.tested" class="muted">연결 시험 {{when(x.tested.t)}}: <span v-if="x.tested.ok" style="color:var(--ok)">성공</span><span v-else style="color:var(--bad)">{{x.tested.msg}}</span></span>
      </div>
    </template>
  </div>`,
};

export default {
  components:{ToolCard},
  setup(){
    const r=ref(null),err=ref(null);
    // 상태를 읽지 못하면 화면에 알리고, "상태 다시 읽기"로 다시 읽는다
    const load=async fresh=>{try{r.value=await api("/api/tools"+(fresh?"?fresh=1":""));err.value=null;}catch(e){err.value=e.message;}};
    let stop;
    onMounted(()=>{
      load(true);
      stop=every(2000,async()=>{if(r.value&&r.value.tools.some(x=>x.login&&x.login.running))await load();});
    });
    onUnmounted(()=>stop());
    return {r,err,load,TOOLS};
  },
  template:`<section class="toolsv">
    <div class="card" style="margin-bottom:12px"><strong>AI 도구</strong>
      <div class="muted">자막 읽기, 문장 정리, 쇼츠 후보 고르기에 쓰는 AI 도구입니다. 끈 도구는 쓰지 않고, 스케줄에서 끈 도구로 정한 날은 켜진 도구로 대신합니다. 모델을 비워 두면 도구의 기본 모델을 씁니다.</div>
      <div class="row"><template v-if="r">오늘 자동 작업 도구: <b>{{r.today?TOOLS[r.today]:"없음(모든 도구가 꺼짐)"}}</b></template> <button class="small" @click="load(true)">상태 다시 읽기</button></div>
      <div v-if="err" class="err" style="margin:6px 0 0">도구 상태를 읽지 못했습니다: {{err}}</div>
    </div>
    <div v-if="!r&&!err" class="card muted">도구 상태를 확인하는 중…</div>
    <template v-else><ToolCard v-for="x in r.tools" :key="x.tool" :x="x" @reload="load"/></template>
  </section>`,
};
