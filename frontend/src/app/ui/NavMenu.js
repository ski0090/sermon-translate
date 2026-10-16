// 왼쪽 메뉴: 프로젝트 목록(단계별), 쇼츠(상태별), 음성 영상(상태별), 사용량, 설정(스케줄, AI 도구)과 그 개수
import { computed, onMounted, onUnmounted } from "vue";
import { every } from "@/shared/lib/index.js";
import { nav } from "@/shared/router/index.js";
import { STAGES, projStage } from "@/entities/project/index.js";
import { library, libState, fetchLibrary } from "@/entities/library/index.js";
import {
  SH_STAGES,
  shStage,
  shortsList,
  fetchShortsList,
} from "@/entities/shorts/index.js";
import {
  SV_STAGES,
  svStage,
  sleepList,
  fetchSleepList,
} from "@/entities/sleep-video/index.js";

const tally = (ks) =>
  ks.reduce((c, k) => ((c[k] = (c[k] || 0) + 1), c), { all: ks.length });

export default {
  setup() {
    // 메뉴의 숫자: 그 화면이 아닐 때만 여기서 센다(목록 화면은 몇 초마다 스스로 받는다)
    let stops = [];
    onMounted(() => {
      stops = [
        every(30000, async () => {
          if (nav.route.view !== "shorts")
            shortsList.value = (await fetchShortsList()).items;
        }),
        every(30000, async () => {
          if (nav.route.view !== "sleep")
            sleepList.value = await fetchSleepList();
        }),
        every(30000, async () => {
          if (nav.route.view !== "projects")
            library.value = await fetchLibrary();
        }),
      ];
    });
    onUnmounted(() => stops.forEach((f) => f()));
    const pc = computed(() =>
      library.value
        ? tally(
            library.value.items
              .map((it) => libState(it).stage)
              .concat(library.value.others.map(projStage)),
          )
        : {},
    );
    const sc = computed(() =>
      shortsList.value ? tally(shortsList.value.map(shStage)) : {},
    );
    const vc = computed(() =>
      sleepList.value ? tally(sleepList.value.items.map(svStage)) : {},
    );
    // 프로젝트를 열었으면 들어온 목록의 거르기를 표시한다
    const on = (view, f) => {
      const r = nav.route;
      return view === "projects" && r.view === "work"
        ? nav.listFilter === f
        : r.view === view && r.filter === f;
    };
    const shHref = (f) =>
      "#/shorts/" + f + (nav.shPid ? "/" + encodeURIComponent(nav.shPid) : "");
    return { STAGES, SH_STAGES, SV_STAGES, pc, sc, vc, on, shHref, nav };
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
        <a class="nhead" :class="{on:nav.route.view==='usage'}" href="#/usage">사용량</a>
      </div>
      <div class="ngroup">
        <a class="nhead" href="#/schedule">설정</a>
        <a class="nitem" :class="{on:nav.route.view==='schedule'}" href="#/schedule">스케줄</a>
        <a class="nitem" :class="{on:nav.route.view==='tools'}" href="#/tools">AI 도구</a>
      </div>
    </div>
  </nav>`,
};
