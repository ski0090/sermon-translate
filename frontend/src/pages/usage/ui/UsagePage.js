// 사용량 화면(#/usage): Claude(5시간·주간·Fable 추가 몫), Codex(한도), Antigravity(/usage)와 날짜별·도구별 호출 수·토큰.
// 30초마다 새로 받고, "확인"은 그 도구에 짧게 물어 지금 값을 읽은 뒤 다시 받는다
import { onMounted, onUnmounted, ref } from "vue";
import { every } from "@/shared/lib/index.js";
import { fetchUsage } from "@/entities/usage/index.js";
import { UsageToolCard } from "@/widgets/usage-card/index.js";
import { UsageHistory } from "@/widgets/usage-history/index.js";

export default {
  components: { UsageToolCard, UsageHistory },
  setup() {
    const d = ref(null);
    const load = async () => {
      d.value = await fetchUsage();
    };
    let stop;
    onMounted(() => {
      stop = every(30000, load);
    });
    onUnmounted(() => stop());
    return { d, load };
  },
  template: `<section class="usagev">
    <div v-if="!d" class="card muted">불러오는 중…</div>
    <template v-else>
      <UsageToolCard v-for="t in ['claude','codex','agy']" :key="t" :t="t" :d="d" @checked="load()"/>
      <UsageHistory :d="d"/>
    </template>
  </section>`,
};
