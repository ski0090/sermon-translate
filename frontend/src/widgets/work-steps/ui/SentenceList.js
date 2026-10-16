// 문장 목록(정리와 검수, 음성 단계가 함께 쓴다). 지금 거르기(W.filter)에 맞는 문장만 보이고,
// 영상에서 지금 나오는 문장(W.cursent)을 표시한다
import { computed } from "vue";
import { useWork } from "@/entities/project/index.js";
import { inFilter } from "@/entities/sentence/index.js";
import { SentenceRow } from "@/features/sentence-edit/index.js";

export default {
  props: { tts: Boolean },
  components: { SentenceRow },
  setup() {
    const W = useWork();
    const pm = computed(() =>
      Object.fromEntries(W.plan.map((p) => [p.sid, p])),
    );
    const list = computed(() =>
      W.d.sentences.filter((s) => inFilter(s, W.filter, pm.value[s.id])),
    );
    return { W, pm, list };
  },
  template: `<div><SentenceRow v-for="s in list" :key="s.id" :s="s" :pl="pm[s.id]" :cur="s.id===W.cursent" :tts="tts"/><p v-if="!list.length" class="muted">해당하는 문장이 없습니다.</p></div>`,
};
