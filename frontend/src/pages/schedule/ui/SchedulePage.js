// 스케줄 화면(#/schedule): 날마다 자동 작업(자동 진행의 자막 읽기·문장 정리, 쇼츠 자동 후보)이 쓸 AI 도구와 Claude 사용량(5시간·주간 %)을
// 달력에서 정한다. 정하지 않은 날은 기본값을 쓴다. 30초마다 새로 받아도 고치는 중인 입력 칸은 덮지 않는다(각 입력 줄이 알아서 둔다)
import { onMounted, onUnmounted, ref } from "vue";
import { every } from "@/shared/lib/index.js";
import { fetchSchedule } from "@/entities/schedule/index.js";
import { ScheduleSettings } from "@/widgets/schedule-settings/index.js";
import { ScheduleCalendar } from "@/widgets/schedule-calendar/index.js";

export default {
  components: { ScheduleSettings, ScheduleCalendar },
  setup() {
    const d = ref(null),
      err = ref(null);
    const take = (v) => {
      d.value = v;
    };
    let stop;
    onMounted(() => {
      stop = every(30000, async () => {
        try {
          take(await fetchSchedule());
          err.value = null;
        } catch (e) {
          err.value = e.message;
        }
      });
    });
    onUnmounted(() => stop());
    return { d, err, take };
  },
  template: `<section class="sched">
    <div v-if="err&&!d" class="card"><div class="err">{{err}}</div></div>
    <div v-else-if="!d" class="card muted">불러오는 중…</div>
    <template v-else>
    <ScheduleSettings :d="d" @saved="take"/>
    <ScheduleCalendar :d="d" @saved="take"/>
    </template>
  </section>`,
};
