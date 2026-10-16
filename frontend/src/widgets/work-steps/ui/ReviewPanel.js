// 정리와 검수 단계: 문장 거르기(확인 필요, 자동 수정됨, 길이 초과), AI로 다시 정리, 문장 목록
import { computed } from "vue";
import { useWork } from "@/entities/project/index.js";
import { edited, isOver } from "@/entities/sentence/index.js";
import SentenceList from "./SentenceList.js";

export default {
  components: { SentenceList },
  setup() {
    const W = useWork();
    const counts = computed(() => ({
      check: W.d.sentences.filter((s) => s.check).length,
      ai: W.d.sentences.filter(edited).length,
      over: W.plan.filter(isOver).length,
    }));
    const running = computed(() => !!(W.d.job && W.d.job.running));
    function tidy() {
      if (
        confirm(
          "문장 목록을 AI로 새로 만듭니다. 직접 고친 내용은 사라집니다. 계속할까요?",
        )
      )
        W.startJob("tidy");
    }
    return { W, counts, running, tidy };
  },
  template: `<div>
    <h2>정리와 검수</h2>
    <div class="row"><select v-model="W.filter"><option value="all">전체 ({{W.d.sentences.length}})</option><option value="check">확인 필요 ({{counts.check}})</option><option value="ai">자동 수정됨 ({{counts.ai}})</option><option value="over">길이 초과 ({{counts.over}})</option></select>
      <button class="small" :disabled="running" @click="tidy">AI로 다시 정리</button>
      <span class="muted">글을 고치면 그 문장의 음성은 다시 만듭니다. 그림 위의 <kbd>여기서 나누기</kbd>로 문장을 나눕니다.</span>
      <span style="flex:1"></span><button class="primary" @click="W.go('tts')">음성 만들기로</button></div>
    <SentenceList/>
  </div>`,
};
