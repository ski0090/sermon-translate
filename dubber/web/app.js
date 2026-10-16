// 새 화면(Vue): 왼쪽 메뉴, 사용량, 화면 바꾸기. 주소의 # 뒤가 화면이다(#/projects/<단계>, #/schedule)
import {createApp,computed,onMounted,onUnmounted,ref,watch} from "./vendor/vue.esm-browser.prod.js";
import {api,store,every,when,ago,STAGES,SH_STAGES,libState,projStage,shStage,openOld} from "./lib.js";
import ProjectsView from "./projects.js";
import ScheduleView from "./schedule.js";

function parseRoute(){
  const [,view,filter]=location.hash.split("/");
  if(view==="schedule")return {view:"schedule",filter:"all"};
  return {view:"projects",filter:STAGES.some(x=>x[0]===filter)?filter:"all"};
}
store.route=parseRoute();
addEventListener("hashchange",()=>{store.route=parseRoute();});

const tally=ks=>ks.reduce((c,k)=>(c[k]=(c[k]||0)+1,c),{all:ks.length});

const UsagePanel={
  setup(){
    const u=ref(null),busy=ref(false);
    const load=async()=>{u.value=await api("/api/usage");};
    let stop;onMounted(()=>{stop=every(30000,load);});onUnmounted(()=>stop());
    // AI(claude)를 부를 때마다 받은 5시간·주간 한도 사용률을 남은 비율로 보여 준다
    const parts=computed(()=>{const w=(u.value&&u.value.info&&u.value.info.unifiedWindows)||{};
      return [["five_hour","5시간"],["seven_day","주간"],["seven_day_overage_included","Fable 추가"]].filter(([k])=>w[k]).map(([k,label])=>{
        const left=Math.max(0,Math.round((1-w[k].utilization)*100));
        return {label,left,color:left<20?"var(--bad)":left<40?"var(--warn)":"var(--text)",title:when(w[k].resetsAt)+"에 초기화"};});});
    async function check(){busy.value=true;try{await api("/api/usage/check","POST",{});}catch(e){alert(e.message);}busy.value=false;await load();}
    return {u,parts,busy,check,when,ago};
  },
  template:`<div id="usage">
    <div class="urow"><span>Claude 남은 사용량</span><button class="small" :disabled="busy" @click="check">확인</button></div>
    <div v-if="!u||!u.info">아직 모름</div>
    <template v-else>
      <div v-for="p in parts" :key="p.label" class="urow" :title="p.title"><span>{{p.label}}</span><b :style="{color:p.color}">{{p.left}}%</b></div>
      <div v-if="u.info.status==='rejected'"><b style="color:var(--bad)">한도 도달 ({{when(u.info.resetsAt)}}까지)</b></div>
      <div title="AI를 부를 때마다 갱신됩니다">{{ago(u.t)}} 기준</div>
    </template>
  </div>`,
};

const NavMenu={
  components:{UsagePanel},
  setup(){
    const pc=computed(()=>store.lib?tally(store.lib.items.map(it=>libState(it).stage).concat(store.lib.others.map(projStage))):{});
    const sc=computed(()=>store.shorts?tally(store.shorts.map(shStage)):{});
    const on=(view,f)=>store.route.view===view&&store.route.filter===f;
    // 쇼츠는 지금 화면에서 연다. 같은 주소(8766)라 지금 화면이 기억하는 거르기를 여기서 정해 둔다
    function shorts(f){try{const v=JSON.parse(localStorage.getItem("dubber.nav"))||{};localStorage.setItem("dubber.nav",JSON.stringify({...v,shorts:f}));}catch(e){}openOld("#shorts");}
    return {STAGES,SH_STAGES,pc,sc,on,shorts,store};
  },
  template:`<nav id="menu">
    <div class="brand">설교 영상 한국어 더빙</div>
    <div class="nav">
      <div class="ngroup">
        <a class="nhead" :class="{on:on('projects','all')}" href="#/projects">프로젝트 목록<span class="ncount">{{pc.all}}</span></a>
        <a v-for="[k,n] in STAGES" :key="k" class="nitem" :class="{on:on('projects',k)}" :href="'#/projects/'+k">{{n}}<span class="ncount">{{pc[k]}}</span></a>
      </div>
      <div class="ngroup">
        <a class="nhead" href="/old#shorts" @click.prevent="shorts('all')" title="지금 화면에서 엽니다"><span>쇼츠 <small class="ext">↗</small></span><span class="ncount">{{sc.all}}</span></a>
        <a v-for="[k,n] in SH_STAGES" :key="k" class="nitem" href="/old#shorts" @click.prevent="shorts(k)" title="지금 화면에서 엽니다">{{n}}<span class="ncount">{{sc[k]}}</span></a>
      </div>
      <div class="ngroup">
        <a class="nhead" href="#/schedule">설정</a>
        <a class="nitem" :class="{on:store.route.view==='schedule'}" href="#/schedule">스케줄</a>
      </div>
    </div>
    <UsagePanel/>
  </nav>`,
};

const App={
  components:{NavMenu,ProjectsView,ScheduleView},
  setup(){
    const navOpen=ref(false);
    watch(()=>store.route,()=>{navOpen.value=false;});
    // 메뉴의 숫자: 쇼츠는 늘, 프로젝트는 그 화면이 아닐 때만 여기서 센다(프로젝트 목록 화면은 2초마다 스스로 받는다)
    let stops=[];
    onMounted(()=>{stops=[every(30000,async()=>{store.shorts=(await api("/api/shorts")).items;}),
      every(30000,async()=>{if(store.route.view!=="projects")store.lib=await api("/api/library");})];});
    onUnmounted(()=>stops.forEach(f=>f()));
    const title=computed(()=>store.route.view==="schedule"?"스케줄":"프로젝트 목록");
    return {store,navOpen,title};
  },
  template:`<div :class="{navopen:navOpen}">
    <NavMenu/>
    <div id="main" @click="navOpen=false">
      <header>
        <button id="btnNav" class="small" title="메뉴" @click.stop="navOpen=!navOpen">☰</button>
        <h1>{{title}}</h1>
        <span class="pilot">새 화면(Vue) 시험판 · <a href="/old">지금 화면으로</a></span>
      </header>
      <ScheduleView v-if="store.route.view==='schedule'"/>
      <ProjectsView v-else/>
    </div>
  </div>`,
};

createApp(App).mount("#app");
