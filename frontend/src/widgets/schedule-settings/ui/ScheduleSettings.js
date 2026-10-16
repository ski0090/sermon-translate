// 스케줄 위 카드: 오늘의 도구와 한도, 지금 사용량, 자동 작업 쉼 여부, 설명, 기본값 줄과 Fable 이어 하기 줄(저장하면 saved)
import { when, ago } from "@/shared/lib/index.js";
import { dayLabel, toolName, usagePct } from "@/entities/schedule/index.js";
import { DefaultsForm, FableForm } from "@/features/schedule-edit/index.js";

export default {
  components: { DefaultsForm, FableForm },
  props: ["d"],
  emits: ["saved"],
  setup() {
    return { label: dayLabel, toolName, pct: usagePct, when, ago };
  },
  template: `<div class="card">
      <div class="row" style="justify-content:space-between;margin:0">
        <strong>오늘 {{label(d.today)}}: {{toolName(d.today_tool)}}{{d.today_tool&&d.today_tool!=="claude"?"로 자동 작업 (Claude 한도는 보지 않음)":" · 한도 5시간 "+d.limits.five_hour+"% · 주간 "+d.limits.seven_day+"%"}}</strong>
        <span class="muted">지금 사용량: 5시간 {{pct(d.usage.five_hour.utilization)}} · 주간 {{pct(d.usage.seven_day.utilization)}}{{d.usage_t?" ("+ago(d.usage_t)+" 기준)":""}}</span>
      </div>
      <div class="row"><template v-if="d.pause"><span class="badge warn">자동 작업 쉬는 중</span> <span class="muted">{{d.pause.reason}} {{when(d.pause.until)}}까지</span></template><span v-else class="badge ok">자동 작업 가능</span></div>
      <div class="muted">자동 진행(자막 읽기·문장 정리)과 쇼츠 자동 후보 고르기는 그날의 Claude 사용량이 한도에 닿으면 쉬고, 사용량이 초기화되거나 한도가 더 높은 날이 되면 이어 갑니다. 0%로 정한 날은 자동 작업을 하지 않습니다. 화면에서 직접 누른 작업은 한도와 상관없이 프로젝트 설정의 AI 도구로 합니다. Codex로 정한 날은 자동 작업을 Codex로 하고 Claude 한도(5시간·주간 %)는 보지 않습니다(0%면 쉼). 사용량은 마지막 Claude 호출 때의 값입니다(사용량 화면의 "확인"으로 새로 읽습니다).</div>
      <DefaultsForm :d="d" @saved="$emit('saved',$event)"/>
      <FableForm :d="d" @saved="$emit('saved',$event)"/>
      <div class="muted">Fable은 5시간·주간 사용량을 기본 모델과 함께 쓰고, 그것을 다 쓴 뒤에 쓸 수 있는 별도 주간 몫이 있습니다. 한도가 100%인 날의 자동 작업은 기본 사용량을 다 쓰면 Fable로 이어 가고, 화면에서 직접 누른 작업은 날과 상관없이 한도에 걸리면 Fable로 이어 갑니다.</div>
    </div>`,
};
