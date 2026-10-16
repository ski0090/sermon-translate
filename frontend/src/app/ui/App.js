// 화면 틀: 왼쪽 메뉴, 머리줄(제목과, 화면이 Teleport로 채우는 #hdrSlot), 주소에 맞는 화면 하나
import { computed, ref, watch } from "vue";
import { nav } from "@/shared/router/index.js";
import { ProjectListPage } from "@/pages/project-list/index.js";
import { WorkPage } from "@/pages/work/index.js";
import { ShortsPage } from "@/pages/shorts/index.js";
import { SleepPage } from "@/pages/sleep/index.js";
import { UsagePage } from "@/pages/usage/index.js";
import { ToolsPage } from "@/pages/tools/index.js";
import { SchedulePage } from "@/pages/schedule/index.js";
import NavMenu from "./NavMenu.js";

export default {
  components: {
    NavMenu,
    ProjectListPage,
    ShortsPage,
    SleepPage,
    SchedulePage,
    WorkPage,
    UsagePage,
    ToolsPage,
  },
  setup() {
    const navOpen = ref(false);
    watch(
      () => nav.route,
      () => {
        navOpen.value = false;
      },
    );
    const title = computed(() =>
      nav.route.view === "work"
        ? nav.workName || "프로젝트"
        : {
            schedule: "스케줄",
            shorts: "쇼츠",
            sleep: "음성 영상",
            usage: "사용량",
            tools: "AI 도구",
          }[nav.route.view] || "프로젝트 목록",
    );
    return { nav, navOpen, title };
  },
  template: `<div :class="{navopen:navOpen}">
    <NavMenu/>
    <div id="main" @click="navOpen=false">
      <header>
        <button id="btnNav" class="small" title="메뉴" @click.stop="navOpen=!navOpen">☰</button>
        <h1>{{title}}</h1>
        <div id="hdrSlot" class="hdrslot"></div>
      </header>
      <SchedulePage v-if="nav.route.view==='schedule'"/>
      <ShortsPage v-else-if="nav.route.view==='shorts'"/>
      <SleepPage v-else-if="nav.route.view==='sleep'"/>
      <UsagePage v-else-if="nav.route.view==='usage'"/>
      <ToolsPage v-else-if="nav.route.view==='tools'"/>
      <WorkPage v-else-if="nav.route.view==='work'" :key="nav.route.pid" :pid="nav.route.pid"/>
      <ProjectListPage v-else/>
    </div>
  </div>`,
};
