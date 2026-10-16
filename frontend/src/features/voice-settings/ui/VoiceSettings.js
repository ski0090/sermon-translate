// 음성 단계의 목소리 줄: 목소리 고르기(음성이 있으면 다시 만든다고 묻는다), 들어 보기, 기본 속도
import { computed, ref } from "vue";
import { EditField } from "@/shared/ui/index.js";
import { saveProjectSettings, useWork } from "@/entities/project/index.js";
import { VOICES, voiceSampleUrl } from "../config/voices.js";

export default {
  components: { EditField },
  setup() {
    const W = useWork(),
      d = computed(() => W.d),
      sel = ref(null),
      sample = ref(false);
    const done = computed(() => d.value.sentences.filter((s) => s.tts).length);
    async function setting(body) {
      try {
        await saveProjectSettings(W.pid, body);
      } catch (e) {
        alert(e.message);
      }
      await W.reload();
    }
    function voice(e) {
      if (
        done.value &&
        !confirm(
          "목소리를 바꾸면 모든 문장의 음성을 다시 만듭니다. 계속할까요?",
        )
      ) {
        e.target.value = d.value.settings.voice;
        return;
      }
      setting({ voice: e.target.value });
    }
    function listen() {
      sample.value = true;
      const a = W.play(voiceSampleUrl(sel.value.value));
      a.oncanplay = a.onerror = () => {
        sample.value = false;
      };
    }
    return { d, sel, sample, VOICES, setting, voice, listen };
  },
  template: `<div class="row"><label>목소리 <select ref="sel" :value="d.settings.voice" @change="voice"><option v-for="v in VOICES" :key="v">{{v}}</option></select></label>
        <button class="small" @click="listen">{{sample?"준비 중…":"들어 보기"}}</button>
        <label>기본 속도 <EditField type="number" step="0.05" min="0.8" max="1.5" style="width:80px" :value="d.settings.speed" @save="v=>setting({speed:+v})"/></label>
        <span class="muted">F는 여성, M은 남성 목소리입니다. 바꾸면 모든 문장의 음성을 다시 만듭니다.</span></div>`,
};
