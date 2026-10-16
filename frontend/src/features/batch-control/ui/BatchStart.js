// 자동 진행 시작: 목소리를 고르고 시작(이미 한 적이 있으면 다시 시작). 고르지 않았으면 지난번 목소리를 쓴다
import { computed, ref } from "vue";
import { startBatch } from "../api/batch.js";
import { VOICES } from "../config/voices.js";

export default {
  props: ["b"],
  emits: ["changed"],
  setup(props, { emit }) {
    const picked = ref(null);
    const voice = computed({
      get: () => picked.value || props.b.voice,
      set: (v) => {
        picked.value = v;
      },
    });
    async function start() {
      if (!confirm("끝나지 않은 영상을 모두 차례로 진행합니다. 시작할까요?"))
        return;
      await startBatch(voice.value);
      emit("changed");
    }
    return { VOICES, voice, start };
  },
  template: `<span class="row" style="margin:0">목소리 <select v-model="voice"><option v-for="v in VOICES" :key="v">{{v}}</option></select><button class="primary" @click="start">{{b.total?"다시 시작":"시작"}}</button></span>`,
};
