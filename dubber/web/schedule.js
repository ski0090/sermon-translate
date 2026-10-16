// 스케줄 화면: 날마다 자동 작업(자동 진행의 자막 읽기·문장 정리, 쇼츠 자동 후보)이 쓸 AI 도구와 Claude 사용량(5시간·주간 %)을
// 달력에서 정한다. 정하지 않은 날은 기본값을 쓴다. 30초마다 새로 받아도 고치는 중인 입력 칸은 덮지 않는다
import {computed,onMounted,onUnmounted,reactive,ref,watch} from "./vendor/vue.esm-browser.prod.js";
import {api,every,when,ago,TOOLS} from "./lib.js";

const pad=n=>String(n).padStart(2,"0");
const key=(y,m,d)=>`${y}-${pad(m+1)}-${pad(d)}`;
const label=k=>{const [y,m,d]=k.split("-").map(Number);return `${m}/${d}(${"일월화수목금토"[new Date(y,m-1,d).getDay()]})`;};
const toolName=t=>TOOLS[t]||"없음(모든 도구가 꺼짐)";
const pct=x=>x==null?"모름":Math.round(x*100)+"%";

export default {
  setup(){
    const d=ref(null),err=ref(null);
    const now=new Date(),cal=reactive({y:now.getFullYear(),m:now.getMonth()});
    const sel=reactive(new Set());let last=null;
    const def=reactive({tool:"claude",five_hour:50,seven_day:50,dirty:false});
    const fb=reactive({on:false,limit:100,dirty:false});
    const pick=reactive({tool:"claude",five_hour:50,seven_day:50});
    function take(v){
      d.value=v;
      if(!def.dirty)Object.assign(def,{tool:v.tool||"claude",five_hour:v.default.five_hour,seven_day:v.default.seven_day});
      if(!fb.dirty)Object.assign(fb,{on:v.fable.on,limit:v.fable.limit});
    }
    let stop;
    onMounted(()=>{stop=every(30000,async()=>{try{take(await api("/api/schedule"));err.value=null;}catch(e){err.value=e.message;}});});
    onUnmounted(()=>stop());
    const post=async body=>{try{return await api("/api/schedule","POST",body);}catch(e){alert(e.message);return null;}};
    async function saveDef(){const v=await post({tool:def.tool,default:{five_hour:def.five_hour,seven_day:def.seven_day}});if(v){def.dirty=false;take(v);}}
    async function saveFable(){const v=await post({fable:{on:fb.on,limit:fb.limit}});if(v){fb.dirty=false;take(v);}}

    // 주간 사용량이 초기화되는 날(다음 초기화 시각부터 7일마다)
    const resets=computed(()=>{const r=d.value&&d.value.usage.seven_day.resetsAt;if(!r)return {};const out={};
      for(let k=0;k<10;k++){const t=new Date((r+k*7*86400)*1000);out[key(t.getFullYear(),t.getMonth(),t.getDate())]=t.toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit"});}
      return out;});
    const cells=computed(()=>{
      const v=d.value;if(!v)return [];
      const {y,m}=cal,first=new Date(y,m,1).getDay(),n=new Date(y,m+1,0).getDate(),out=[];
      for(let i=0;i<first;i++)out.push({k:"blank"+i,blank:true});
      for(let day=1;day<=n;day++){const k=key(y,m,day),set=v.days[k],wd=(first+day-1)%7;
        out.push({k,day,set:!!set,lim:set||v.default,tool:(set&&set.tool)||v.tool||"claude",wd,past:k<v.today,today:k===v.today,reset:resets.value[k]});}
      return out;
    });
    function month(dm){if(dm===0){cal.y=now.getFullYear();cal.m=now.getMonth();return;}
      cal.m+=dm;if(cal.m<0){cal.m=11;cal.y--;}if(cal.m>11){cal.m=0;cal.y++;}}
    function clickDay(c,e){
      if(c.blank||c.past)return;
      if(e.shiftKey&&last){const [a,b]=[last,c.k].sort();
        for(let t=new Date(a+"T12:00");;t.setDate(t.getDate()+1)){const kk=key(t.getFullYear(),t.getMonth(),t.getDate());if(kk>b)break;sel.add(kk);}}
      else if(sel.has(c.k))sel.delete(c.k);else sel.add(c.k);
      last=c.k;
    }
    const weekends=()=>cells.value.forEach(c=>{if(!c.blank&&!c.past&&(c.wd===0||c.wd===6))sel.add(c.k);});
    const days=computed(()=>[...sel].sort());
    // 고른 날의 입력 칸은 처음 고른 날의 값으로 채운다
    watch(()=>days.value[0],k=>{if(!k||!d.value)return;const v=d.value.days[k]||d.value.default;
      Object.assign(pick,{tool:v.tool||d.value.tool||"claude",five_hour:v.five_hour,seven_day:v.seven_day});});
    async function send(x){const v=await post({days:x});if(v){sel.clear();take(v);}}
    const apply=()=>send(Object.fromEntries(days.value.map(k=>[k,{tool:pick.tool,five_hour:pick.five_hour,seven_day:pick.seven_day}])));
    const reset=()=>send(Object.fromEntries(days.value.map(k=>[k,null])));
    return {d,err,cal,sel,def,fb,pick,saveDef,saveFable,cells,month,clickDay,weekends,days,apply,reset,label,toolName,pct,when,ago,TOOLS};
  },
  template:`<section class="sched">
    <div v-if="err&&!d" class="card"><div class="err">{{err}}</div></div>
    <div v-else-if="!d" class="card muted">불러오는 중…</div>
    <template v-else>
    <div class="card">
      <div class="row" style="justify-content:space-between;margin:0">
        <strong>오늘 {{label(d.today)}}: {{toolName(d.today_tool)}}{{d.today_tool&&d.today_tool!=="claude"?"로 자동 작업 (Claude 한도는 보지 않음)":" · 한도 5시간 "+d.limits.five_hour+"% · 주간 "+d.limits.seven_day+"%"}}</strong>
        <span class="muted">지금 사용량: 5시간 {{pct(d.usage.five_hour.utilization)}} · 주간 {{pct(d.usage.seven_day.utilization)}}{{d.usage_t?" ("+ago(d.usage_t)+" 기준)":""}}</span>
      </div>
      <div class="row"><template v-if="d.pause"><span class="badge warn">자동 작업 쉬는 중</span> <span class="muted">{{d.pause.reason}} {{when(d.pause.until)}}까지</span></template><span v-else class="badge ok">자동 작업 가능</span></div>
      <div class="muted">자동 진행(자막 읽기·문장 정리)과 쇼츠 자동 후보 고르기는 그날의 Claude 사용량이 한도에 닿으면 쉬고, 사용량이 초기화되거나 한도가 더 높은 날이 되면 이어 갑니다. 0%로 정한 날은 자동 작업을 하지 않습니다. 화면에서 직접 누른 작업은 한도와 상관없이 프로젝트 설정의 AI 도구로 합니다. Codex로 정한 날은 자동 작업을 Codex로 하고 Claude 한도(5시간·주간 %)는 보지 않습니다(0%면 쉼). 사용량은 마지막 Claude 호출 때의 값입니다(왼쪽 아래의 "확인"으로 새로 읽습니다).</div>
      <div class="row" style="margin-top:10px">기본 도구 <select v-model="def.tool" @change="def.dirty=true"><option v-for="(n,k) in TOOLS" :key="k" :value="k">{{n}}</option></select>
        기본 한도 <label>5시간 <input type="number" min="0" max="100" step="5" v-model.number="def.five_hour" @input="def.dirty=true" style="width:70px">%</label>
        <label>주간 <input type="number" min="0" max="100" step="5" v-model.number="def.seven_day" @input="def.dirty=true" style="width:70px">%</label>
        <button class="small" @click="saveDef">기본값 저장</button><span class="muted">달력에서 정하지 않은 날에 씁니다.</span></div>
      <div class="row" style="margin-top:4px"><label><input type="checkbox" v-model="fb.on" @change="saveFable"> 기본 사용량을 다 쓰면 Fable로 이어 하기</label>
        <label>Fable 추가 몫 한도 <input type="number" min="0" max="100" step="5" v-model.number="fb.limit" @input="fb.dirty=true" style="width:70px">%</label>
        <button class="small" @click="saveFable">저장</button>
        <span class="muted">Fable 추가 몫 지금 {{pct((d.usage.seven_day_overage_included||{}).utilization)}} 사용{{(d.usage.seven_day_overage_included||{}).resetsAt?" · "+when(d.usage.seven_day_overage_included.resetsAt)+" 초기화":""}}</span>
        <span v-if="d.fable_now" class="badge ok">지금 Fable로 작업 중</span></div>
      <div class="muted">Fable은 5시간·주간 사용량을 기본 모델과 함께 쓰고, 그것을 다 쓴 뒤에 쓸 수 있는 별도 주간 몫이 있습니다. 한도가 100%인 날의 자동 작업은 기본 사용량을 다 쓰면 Fable로 이어 가고, 화면에서 직접 누른 작업은 날과 상관없이 한도에 걸리면 Fable로 이어 갑니다.</div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="row" style="justify-content:space-between;margin:0">
        <span class="row" style="margin:0"><button class="small" @click="month(-1)">◀</button><strong style="min-width:7em;text-align:center">{{cal.y}}년 {{cal.m+1}}월</strong><button class="small" @click="month(1)">▶</button><button class="small" @click="month(0)">이번 달</button></span>
        <span class="row" style="margin:0"><button class="small" @click="weekends">이 달 주말 고르기</button><span class="muted"><span class="badge" style="background:var(--accent2);color:var(--accent)">파란 날</span>은 따로 정한 날</span></span>
      </div>
      <div class="cal">
        <div v-for="(w,i) in '일월화수목금토'" :key="w" class="cw" :class="{sun:i===0,sat:i===6}">{{w}}</div>
        <div v-for="c in cells" :key="c.k" class="cd" :class="c.blank?'blank':{sun:c.wd===0,sat:c.wd===6,past:c.past,today:c.today,set:c.set,sel:sel.has(c.k)}" @click="clickDay(c,$event)">
          <template v-if="!c.blank">
            <div class="cdn">{{c.day}} <span v-if="c.today" class="badge ok">오늘</span></div>
            <div class="cdv"><template v-if="c.tool==='claude'">Claude</template><b v-else style="color:#047857">{{TOOLS[c.tool]}}</b><br>5시간 {{c.lim.five_hour}}%<br>주간 {{c.lim.seven_day}}%</div>
            <div v-if="c.reset" class="cdr" title="Claude 주간 사용량이 초기화되는 시각">↻ 주간 초기화 {{c.reset}}</div>
          </template>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <span v-if="!days.length" class="muted">날짜를 누르면 고릅니다. Shift를 누른 채 누르면 그 사이의 날을 모두 고릅니다. 고른 날의 한도를 정하고 "적용"을 누르세요.</span>
      <template v-else>
        <div class="row" style="margin:0"><strong>고른 날 {{days.length}}일</strong><span class="muted">{{days.slice(0,8).map(label).join(", ")}}{{days.length>8?" …":""}}</span></div>
        <div class="row">도구 <select v-model="pick.tool"><option v-for="(n,k) in TOOLS" :key="k" :value="k">{{n}}</option></select>
          <label>5시간 <input type="number" min="0" max="100" step="5" v-model.number="pick.five_hour" style="width:70px">%</label>
          <label>주간 <input type="number" min="0" max="100" step="5" v-model.number="pick.seven_day" style="width:70px">%</label>
          <button class="primary small" @click="apply">적용</button><button class="small" @click="reset">기본값으로</button><button class="small" @click="sel.clear()">고르기 취소</button></div>
      </template>
    </div>
    </template>
  </section>`,
};
