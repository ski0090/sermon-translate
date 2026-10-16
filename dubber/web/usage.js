// 사용량 화면: Claude(5시간·주간·Fable 추가 몫), Codex(한도), Antigravity(/usage)와 날짜별·도구별 호출 수·토큰.
// 30초마다 새로 받고, "확인"은 그 도구에 짧게 물어 지금 값을 읽는다
import {computed,onMounted,onUnmounted,reactive,ref} from "./vendor/vue.esm-browser.prod.js";
import {api,every,when} from "./lib.js";

const ago=t=>{if(!t)return "아직 모름";const m=Math.round((Date.now()/1000-t)/60);return m<1?"방금":m<60?m+"분 전":m<1440?Math.round(m/60)+"시간 전":Math.round(m/1440)+"일 전";};
const span=m=>!m?"":m>=1440?Math.round(m/1440)+"일":m>=60?Math.round(m/60)+"시간":m+"분";
const tok=n=>!n?"0":n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?Math.round(n/1e3)+"K":String(n);

// 한도 막대 하나: 쓴 비율(0~1), 초기화 시각, 덧붙임 말
const UsageBar={
  props:["label","used","resets","note"],
  setup(props){
    const p=computed(()=>Math.round(props.used*100));
    const color=computed(()=>p.value>=90?"var(--bad)":p.value>=70?"var(--warn)":"var(--accent)");
    return {p,color,when};
  },
  template:`<div class="uvrow"><span class="uvlab">{{label}}</span>
    <span v-if="used==null" class="muted">모름</span>
    <template v-else><div class="uvbar"><i :style="{width:Math.min(100,p)+'%',background:color}"></i></div>
      <span class="uvval"><b>{{p}}%</b> 사용 · 남음 {{Math.max(0,100-p)}}%</span><span class="muted">{{resets?when(resets)+" 초기화":""}}{{note?" · "+note:""}}</span></template>
  </div>`,
};

export default {
  components:{UsageBar},
  setup(){
    const d=ref(null),busy=reactive({});
    const load=async()=>{d.value=await api("/api/usage/all");};
    let stop;onMounted(()=>{stop=every(30000,load);});onUnmounted(()=>stop());
    async function check(tool){busy[tool]=true;try{await api("/api/usage/all/check","POST",{tool});}catch(e){alert(e.message);}busy[tool]=false;await load();}
    const cw=computed(()=>(d.value&&d.value.claude.windows)||{});
    const cx=computed(()=>(d.value&&d.value.codex.limits)||{});
    const card=t=>({claude:d.value.claude.t,codex:d.value.codex.t,agy:(d.value.agy||{}).t})[t];
    return {d,busy,check,cw,cx,card,ago,span,tok};
  },
  template:`<section class="usagev">
    <div v-if="!d" class="card muted">불러오는 중…</div>
    <template v-else>
      <div v-for="t in ['claude','codex','agy']" :key="t" class="card" style="margin-bottom:12px">
        <div class="row" style="justify-content:space-between;margin:0">
          <strong>{{d.names[t]}} <span v-if="d.today===t" class="badge ok">오늘 자동 작업 도구</span></strong>
          <span class="row" style="margin:0"><span class="muted">{{ago(card(t))}} 기준</span><button class="small" :disabled="busy[t]" @click="check(t)">{{busy[t]?"확인 중…":"확인"}}</button></span>
        </div>
        <template v-if="t==='claude'">
          <UsageBar label="5시간" :used="(cw.five_hour||{}).utilization" :resets="(cw.five_hour||{}).resetsAt"/>
          <UsageBar label="주간" :used="(cw.seven_day||{}).utilization" :resets="(cw.seven_day||{}).resetsAt"/>
          <UsageBar label="Fable 추가 몫" :used="(cw.seven_day_overage_included||{}).utilization" :resets="(cw.seven_day_overage_included||{}).resetsAt" note="주간 사용량을 다 쓴 뒤 Fable로 쓰는 몫"/>
          <div v-if="d.claude.status==='rejected'" class="err" style="margin:6px 0 0">지금 한도에 걸려 있습니다</div>
        </template>
        <template v-else-if="t==='codex'">
          <template v-if="cx.primary||cx.secondary">
            <UsageBar v-if="cx.primary" :label="'한도 ('+span(cx.primary.window_minutes)+')'" :used="cx.primary.used_percent/100" :resets="cx.primary.resets_at"/>
            <UsageBar v-if="cx.secondary" :label="'두 번째 한도 ('+span(cx.secondary.window_minutes)+')'" :used="cx.secondary.used_percent/100" :resets="cx.secondary.resets_at"/>
          </template>
          <div v-else class="muted">아직 기록이 없습니다. "확인"을 누르면 아주 짧게 한 번 불러 봅니다.</div>
          <div v-if="cx.credits&&cx.credits.has_credits" class="muted">크레딧 {{cx.credits.balance}}</div>
          <div v-if="d.codex.model" class="muted">마지막 모델 {{d.codex.model}}</div>
        </template>
        <template v-else>
          <pre v-if="(d.agy||{}).text" class="tlcode">{{d.agy.text}}</pre>
          <div v-else class="muted">"확인"을 누르면 agy에 /usage(모델 할당량)를 물어봅니다. Antigravity가 설치·로그인되어 있어야 합니다.</div>
        </template>
      </div>
      <div class="card"><strong>날짜별 사용 (최근 14일)</strong>
        <template v-if="d.days.length">
          <table class="uvtab">
            <tr><th>날짜</th><th v-for="(n,t) in d.names" :key="t">{{n}}</th></tr>
            <tr v-for="[day,v] in d.days" :key="day"><td>{{day}}</td>
              <td v-for="(n,t) in d.names" :key="t"><template v-if="v[t]">{{v[t].calls}}회<span v-if="v[t].fails" style="color:var(--bad)"> (실패 {{v[t].fails}})</span><div class="muted">{{tok(v[t].in)}} / {{tok(v[t].out)}}</div></template><span v-else class="muted">-</span></td>
            </tr>
          </table>
          <div class="muted">호출 수(실패 수)와 토큰(보낸 것 / 받은 것). 이 앱이 부른 것만 셉니다.</div>
        </template>
        <div v-else class="muted">아직 기록이 없습니다.</div>
      </div>
    </template>
  </section>`,
};
