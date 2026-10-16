// 음성 단계: 목소리와 기본 속도, 음성 만들기, 영상과 함께 미리 듣기, 문장별로 들어 보고 속도·앞 쉼 바꾸기와 다시 만들기
import { computed } from "vue";
import { useWork } from "@/entities/project/index.js";
import { isOver } from "@/entities/sentence/index.js";
import { VoiceSettings } from "@/features/voice-settings/index.js";
import SentenceList from "./SentenceList.js";

export default {
  components: { SentenceList, VoiceSettings },
  setup() {
    const W = useWork(),
      d = computed(() => W.d);
    const done = computed(() => d.value.sentences.filter((s) => s.tts).length),
      total = computed(() => d.value.sentences.length);
    const over = computed(() => W.plan.filter(isOver).length);
    const running = computed(() => !!(d.value.job && d.value.job.running));
    return {
      W,
      done,
      total,
      over,
      running,
      make: () => W.startJob("tts", { force: done.value >= total.value }),
    };
  },
  template: `<div>
    <h2>음성</h2>
    <div class="card">
      <VoiceSettings/>
      <div class="row"><button class="primary" :disabled="running" @click="make">{{done<total?"음성 만들기 ("+(total-done)+"문장 남음)":"음성 모두 만들어짐 · 다시 만들기"}}</button>
        <span class="stat">{{done}}/{{total}} 문장</span><span v-if="over" class="badge warn">길이 초과 {{over}}문장</span>
        <button class="small" @click="W.setPreview(!W.preview)">{{W.preview?"미리 듣기 끄기":"영상과 함께 미리 듣기"}}</button>
        <span style="flex:1"></span><button class="primary" :disabled="!done" @click="W.go('export')">내보내기로</button></div>
    </div>
    <div class="row"><select v-model="W.filter"><option value="all">전체</option><option value="over">길이 초과만</option><option value="check">확인 필요만</option></select><span class="muted">문장별로 들어 보고 속도나 앞 쉼을 바꾸거나 다시 만들 수 있습니다.</span></div>
    <SentenceList tts/>
  </div>`,
};
