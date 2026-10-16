// 음성 영상(자면서 듣는 설교) 화면(#/sleep/<상태>): 음성을 만든 영상마다 이퀄라이저 화면 + 싱크 없이 이은 음성 영상을 만들고,
// 재생·내려받기·유튜브 올리기를 한다. 메뉴에서 고른 상태만 보이고, 3초마다 새로 받아도 재생 중인 영상은 끊기지 않는다
import { computed, onMounted, onUnmounted } from "vue";
import { every } from "@/shared/lib/index.js";
import { nav } from "@/shared/router/index.js";
import { sleepList, fetchSleepList } from "@/entities/sleep-video/index.js";
import { SleepHeader, SleepList } from "@/widgets/sleep-list/index.js";

export default {
  components: { SleepHeader, SleepList },
  setup() {
    const load = async () => {
      sleepList.value = await fetchSleepList();
    };
    let stop;
    onMounted(() => {
      stop = every(3000, load);
    });
    onUnmounted(() => stop());
    return { d: computed(() => sleepList.value), nav, load };
  },
  template: `<section class="sleepv">
    <div v-if="!d" class="card muted">불러오는 중…</div>
    <template v-else>
    <SleepHeader :d="d" @changed="load()"/>
    <SleepList :d="d" :filter="nav.route.filter" @changed="load()"/>
    </template>
  </section>`,
};
