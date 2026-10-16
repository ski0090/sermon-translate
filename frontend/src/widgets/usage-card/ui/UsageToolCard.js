// AI 도구 하나(t: claude, codex, agy)의 사용량 카드: 이름과 오늘 자동 작업 도구 표시, 읽은 때와 "확인",
// Claude는 5시간·주간·Fable 추가 몫 막대, Codex는 한도 막대·크레딧·마지막 모델, Antigravity는 /usage 글
import { computed } from "vue";
import { UsageBar, since, span } from "@/entities/usage/index.js";
import { UsageCheckButton } from "@/features/usage-check/index.js";

export default {
  components: { UsageBar, UsageCheckButton },
  props: ["t", "d"],
  emits: ["checked"],
  setup(props) {
    const cw = computed(() => props.d.claude.windows || {});
    const cx = computed(() => props.d.codex.limits || {});
    // 이 도구의 사용량을 마지막으로 읽은 때
    const read = computed(
      () =>
        ({
          claude: props.d.claude.t,
          codex: props.d.codex.t,
          agy: (props.d.agy || {}).t,
        })[props.t],
    );
    return { cw, cx, read, since, span };
  },
  template: `<div class="card" style="margin-bottom:12px">
        <div class="row" style="justify-content:space-between;margin:0">
          <strong>{{d.names[t]}} <span v-if="d.today===t" class="badge ok">오늘 자동 작업 도구</span></strong>
          <span class="row" style="margin:0"><span class="muted">{{since(read)}} 기준</span><UsageCheckButton :tool="t" @checked="$emit('checked')"/></span>
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
      </div>`,
};
