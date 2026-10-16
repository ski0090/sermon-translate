// 머리줄의 단계 단추(1. 자막 읽기 · 2. 정리와 검수 · 3. 음성 · 4. 내보내기). 서버가 적은 단계까지는 끝난 것으로 보이고,
// 문장이 있으면 정리와 검수·음성, 음성이 하나라도 있으면 내보내기를 열 수 있다
import { computed } from "vue";
import { STEPS, STEP_ORDER, useWork } from "@/entities/project/index.js";

export default {
  setup() {
    const W = useWork();
    const steps = computed(() => {
      const d = W.d;
      if (!d) return [];
      const furthest = STEP_ORDER.indexOf(d.step);
      return STEPS.map(([k, n], i) => {
        const idx = i + 1;
        return {
          k,
          n,
          idx,
          done: idx <= furthest,
          avail:
            idx <= Math.max(furthest, 1) ||
            (k === "review" && d.sentences.length) ||
            (k === "tts" && d.sentences.length) ||
            (k === "export" && d.sentences.some((s) => s.tts)),
        };
      });
    });
    return { W, steps };
  },
  template: `<nav class="steps"><button v-for="s in steps" :key="s.k" :class="{active:s.k===W.step,done:s.done}" :disabled="!s.avail" @click="W.go(s.k)">{{s.idx}}. {{s.n}}</button></nav>`,
};
