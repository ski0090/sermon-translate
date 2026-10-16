// 자동 진행 카드: 켜져 있으면 지금 하는 영상과 대기열, 꺼져 있으면 설명과 시작. 실패한 영상과 건너뛴 영상도 보인다
import { computed } from "vue";
import { when } from "@/shared/lib/index.js";
import { batchSummary } from "@/entities/batch/index.js";
import { BatchStart, BatchStop } from "@/features/batch-control/index.js";

export default {
  components: { BatchStart, BatchStop },
  props: ["b"],
  emits: ["changed"],
  setup(props) {
    const sum = computed(() => batchSummary(props.b));
    return { sum, when };
  },
  template: `<div class="card" style="margin-top:16px">
    <template v-if="b.on">
      <div class="row" style="justify-content:space-between;margin:0"><strong>자동 진행 중 <span class="badge ok">목소리 {{b.voice}}</span></strong><BatchStop @changed="$emit('changed')"/></div>
      <div class="muted">{{sum}}</div>
      <div v-if="b.current.prep" class="muted">자막 읽기: <b>{{b.current.prep.name}}</b> {{b.current.prep.msg||""}}</div>
      <div v-for="v in b.current.voice||[]" :key="v.name" class="muted">음성·내보내기: <b>{{v.name}}</b> {{v.msg||""}}</div>
      <div v-if="b.wait_until" class="muted" style="color:var(--warn)">{{b.wait_reason||"Claude 사용량 한도로"}} 자막 읽기를 {{when(b.wait_until)}}까지 쉬는 중 (음성은 계속)</div>
    </template>
    <template v-else>
      <div class="row" style="justify-content:space-between;margin:0"><div><strong>자동 진행</strong><div class="muted">끝나지 않은 JP 영상을 번호순으로 자막 읽기와 문장 정리까지 진행합니다. 검수한 뒤 음성은 각 영상에서 "음성 만들기"를 눌러 시작합니다(음성 대기열에서 4편씩 만듭니다).</div></div>
        <BatchStart :b="b" @changed="$emit('changed')"/></div>
      <div v-if="sum" class="muted">{{sum}}</div>
      <div v-if="b.stopped_reason" class="err" style="margin:6px 0">{{b.stopped_reason}}</div>
    </template>
    <div v-if="b.errors.length" class="muted" style="color:var(--bad)"><div v-for="e in b.errors" :key="e.name">{{e.name}}: {{e.error}}</div></div>
    <details v-if="(b.skipped||[]).length" class="muted"><summary>같은 영상이라 건너뛴 {{b.skipped.length}}편 (드라이브의 제목을 확인하세요)</summary><div v-for="x in b.skipped" :key="x.name">{{x.name}} = {{x.same_as}}</div></details>
  </div>`,
};
