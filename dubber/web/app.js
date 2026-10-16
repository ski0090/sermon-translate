// 화면(Vue): 왼쪽 메뉴와 화면 바꾸기. 주소의 # 뒤가 화면이다(#/projects/<단계>, #/shorts/<상태>/<프로젝트>, #/sleep/<상태>, #/usage, #/schedule, #/tools, #/p/<프로젝트>)
import {
  createApp,
  computed,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from "./vendor/vue.esm-browser.prod.js";
import {
  api,
  store,
  every,
  STAGES,
  SH_STAGES,
  SV_STAGES,
  libState,
  projStage,
  shStage,
  svStage,
} from "./lib.js";
import ProjectsView from "./projects.js";
import ShortsView from "./shorts.js";
import SleepView from "./sleep.js";
import WorkView from "./work.js";
import UsageView from "./usage.js";
import ToolsView from "./tools.js";
import ScheduleView from "./schedule.js";

const known = (list, f) => (list.some((x) => x[0] === f) ? f : "all");
function parseRoute() {
  const [view, filter, pid] = location.hash.replace(/^#\/?/, "").split("/");
  if (view === "p")
    return {
      view: "work",
      filter: "all",
      pid: decodeURIComponent(filter || ""),
    };
  if (["schedule", "usage", "tools"].includes(view))
    return { view, filter: "all" };
  if (view === "shorts")
    return {
      view,
      filter: known(SH_STAGES, filter),
      pid: pid ? decodeURIComponent(pid) : null,
    };
  if (view === "sleep") return { view, filter: known(SV_STAGES, filter) };
  return { view: "projects", filter: known(STAGES, filter) };
}
// 쇼츠에서 고른 영상과 프로젝트 목록의 거르기는 다른 화면에 다녀와도 기억한다
const route = () => {
  const r = (store.route = parseRoute());
  if (r.view === "shorts" && r.pid) store.shPid = r.pid;
  if (r.view === "projects") store.listFilter = r.filter;
};
route();
addEventListener("hashchange", route);

const tally = (ks) =>
  ks.reduce((c, k) => ((c[k] = (c[k] || 0) + 1), c), { all: ks.length });

const NavMenu = {
  setup() {
    const pc = computed(() =>
      store.lib
        ? tally(
            store.lib.items
              .map((it) => libState(it).stage)
              .concat(store.lib.others.map(projStage)),
          )
        : {},
    );
    const sc = computed(() =>
      store.shorts ? tally(store.shorts.map(shStage)) : {},
    );
    const vc = computed(() =>
      store.sleep ? tally(store.sleep.items.map(svStage)) : {},
    );
    // 프로젝트를 열었으면 들어온 목록의 거르기를 표시한다
    const on = (view, f) => {
      const r = store.route;
      return view === "projects" && r.view === "work"
        ? store.listFilter === f
        : r.view === view && r.filter === f;
    };
    const shHref = (f) =>
      "#/shorts/" +
      f +
      (store.shPid ? "/" + encodeURIComponent(store.shPid) : "");
    return { STAGES, SH_STAGES, SV_STAGES, pc, sc, vc, on, shHref, store };
  },
  template: `<nav id="menu">
    <div class="brand">설교 영상 한국어 더빙</div>
    <div class="nav">
      <div class="ngroup">
        <a class="nhead" :class="{on:on('projects','all')}" href="#/projects">프로젝트 목록<span class="ncount">{{pc.all}}</span></a>
        <a v-for="[k,n] in STAGES" :key="k" class="nitem" :class="{on:on('projects',k)}" :href="'#/projects/'+k">{{n}}<span class="ncount">{{pc[k]}}</span></a>
      </div>
      <div class="ngroup">
        <a class="nhead" :class="{on:on('shorts','all')}" :href="shHref('all')">쇼츠<span class="ncount">{{sc.all}}</span></a>
        <a v-for="[k,n] in SH_STAGES" :key="k" class="nitem" :class="{on:on('shorts',k)}" :href="shHref(k)">{{n}}<span class="ncount">{{sc[k]}}</span></a>
      </div>
      <div class="ngroup">
        <a class="nhead" :class="{on:on('sleep','all')}" href="#/sleep">음성 영상<span class="ncount">{{vc.all}}</span></a>
        <a v-for="[k,n] in SV_STAGES" :key="k" class="nitem" :class="{on:on('sleep',k)}" :href="'#/sleep/'+k">{{n}}<span class="ncount">{{vc[k]}}</span></a>
      </div>
      <div class="ngroup">
        <a class="nhead" :class="{on:store.route.view==='usage'}" href="#/usage">사용량</a>
      </div>
      <div class="ngroup">
        <a class="nhead" href="#/schedule">설정</a>
        <a class="nitem" :class="{on:store.route.view==='schedule'}" href="#/schedule">스케줄</a>
        <a class="nitem" :class="{on:store.route.view==='tools'}" href="#/tools">AI 도구</a>
      </div>
    </div>
  </nav>`,
};

const App = {
  components: {
    NavMenu,
    ProjectsView,
    ShortsView,
    SleepView,
    ScheduleView,
    WorkView,
    UsageView,
    ToolsView,
  },
  setup() {
    const navOpen = ref(false);
    watch(
      () => store.route,
      () => {
        navOpen.value = false;
      },
    );
    // 메뉴의 숫자: 그 화면이 아닐 때만 여기서 센다(목록 화면은 몇 초마다 스스로 받는다)
    let stops = [];
    onMounted(() => {
      stops = [
        every(30000, async () => {
          if (store.route.view !== "shorts")
            store.shorts = (await api("/api/shorts")).items;
        }),
        every(30000, async () => {
          if (store.route.view !== "sleep")
            store.sleep = await api("/api/sleep");
        }),
        every(30000, async () => {
          if (store.route.view !== "projects")
            store.lib = await api("/api/library");
        }),
      ];
    });
    onUnmounted(() => stops.forEach((f) => f()));
    const title = computed(() =>
      store.route.view === "work"
        ? store.workName || "프로젝트"
        : {
            schedule: "스케줄",
            shorts: "쇼츠",
            sleep: "음성 영상",
            usage: "사용량",
            tools: "AI 도구",
          }[store.route.view] || "프로젝트 목록",
    );
    return { store, navOpen, title };
  },
  template: `<div :class="{navopen:navOpen}">
    <NavMenu/>
    <div id="main" @click="navOpen=false">
      <header>
        <button id="btnNav" class="small" title="메뉴" @click.stop="navOpen=!navOpen">☰</button>
        <h1>{{title}}</h1>
        <div id="hdrSlot" class="hdrslot"></div>
      </header>
      <ScheduleView v-if="store.route.view==='schedule'"/>
      <ShortsView v-else-if="store.route.view==='shorts'"/>
      <SleepView v-else-if="store.route.view==='sleep'"/>
      <UsageView v-else-if="store.route.view==='usage'"/>
      <ToolsView v-else-if="store.route.view==='tools'"/>
      <WorkView v-else-if="store.route.view==='work'" :key="store.route.pid" :pid="store.route.pid"/>
      <ProjectsView v-else/>
    </div>
  </div>`,
};

createApp(App).mount("#app");
