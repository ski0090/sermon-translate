// 자막 읽기 단계: 자막 읽기 시작, 읽은 결과 요약, 자막 영역(빨간 상자) 편집
import { computed } from "vue";
import { useWork } from "@/entities/project/index.js";
import { CaptionAreaEditor } from "@/features/caption-area/index.js";

export default {
  components: { CaptionAreaEditor },
  setup() {
    const W = useWork(),
      d = computed(() => W.d);
    const n = computed(() => d.value.captions.length),
      empty = computed(() => d.value.captions.filter((c) => !c.text).length);
    const running = computed(() => !!(d.value.job && d.value.job.running));
    function scan() {
      if (
        n.value &&
        !confirm(
          "자막을 다시 읽으면 지금까지 정리한 문장이 초기화됩니다. 계속할까요?",
        )
      )
        return;
      W.startJob("scan", { auto_roi: !d.value.roi });
    }
    return { W, d, n, empty, running, scan };
  },
  template: `<div>
    <h2>자막 읽기</h2>
    <p class="muted">자막이 바뀌는 순간을 PC 안에서 찾은 뒤, 자막 그림을 {{d.settings.per_strip}}장씩 묶어 AI({{d.settings.tool}})에 읽힙니다. 영상 자체는 전송하지 않습니다. 영상을 재생할 필요는 없습니다.</p>
    <div class="row" style="margin:0 0 12px">
      <button class="primary" :disabled="running" @click="scan">{{n?"자막 다시 읽기":"자막 읽기 시작"}}</button>
      <span class="muted">{{n?"자막 "+n+"장 읽음 · 글이 비어 있는 자막 "+empty+"장":"영상 전체를 훑고 AI 읽기까지 이어서 진행합니다."}}</span>
    </div>
    <template v-if="n">
      <div class="row"><span class="stat">자막 없음 구간 {{d.ranges.gaps.length}}개</span><span class="stat">찬양 후보 구간 {{d.ranges.lyrics.length}}개</span><span class="stat">잘라내기 {{d.cuts.length}}개</span><span class="muted">아래 타임라인에서 확인하고 잘라낼 구간을 정하세요.</span></div>
      <div class="row" style="margin-bottom:12px"><button class="primary" :disabled="!d.sentences.length" @click="W.go('review')">정리와 검수로</button></div>
    </template>
    <CaptionAreaEditor/>
  </div>`,
};
