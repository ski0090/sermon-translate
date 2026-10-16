// 프로젝트 설정 창: AI 도구, 자막 읽기 묶음, 자막 없음 기준, AI 문장 정리, 음성 합성 품질, 읽기 사전.
// 음성 합성 품질을 바꾸면 모든 문장의 음성을 다시 만들므로 한 번 더 묻는다
import { reactive } from "vue";
import { ModalCard } from "@/shared/ui/index.js";
import { saveProjectSettings, useWork } from "@/entities/project/index.js";
import { TOOLS } from "@/entities/ai-tool/index.js";

export default {
  components: { ModalCard },
  emits: ["close"],
  setup(_, { emit }) {
    const W = useWork(),
      s = W.d.settings;
    const f = reactive({
      tool: s.tool,
      per_strip: s.per_strip,
      workers: s.workers,
      min_gap: s.min_gap,
      ai_tidy: !!s.ai_tidy,
      tts_steps: String(s.tts_steps || 8),
      dict: Object.entries(s.dictionary || {})
        .map(([k, v]) => k + "=" + v)
        .join("\n"),
    });
    async function save() {
      const dictionary = {};
      f.dict.split("\n").forEach((l) => {
        const i = l.indexOf("=");
        if (i > 0) dictionary[l.slice(0, i).trim()] = l.slice(i + 1).trim();
      });
      const body = {
        tool: f.tool,
        per_strip: +f.per_strip,
        workers: +f.workers,
        min_gap: +f.min_gap,
        ai_tidy: f.ai_tidy,
        dictionary,
      };
      if (String(s.tts_steps || 8) !== f.tts_steps) {
        if (
          !confirm(
            "음성 합성 품질을 바꾸면 모든 문장의 음성을 다시 만듭니다. 계속할까요?",
          )
        )
          return;
        body.tts_steps = +f.tts_steps;
      }
      try {
        await saveProjectSettings(W.pid, body);
      } catch (e) {
        return alert(e.message);
      }
      emit("close");
      await W.reload();
    }
    return { f, save, TOOLS };
  },
  template: `<ModalCard>
    <h2 style="margin-top:0">프로젝트 설정</h2>
    <label>AI 도구</label>
    <select v-model="f.tool"><option v-for="(n,k) in TOOLS" :key="k" :value="k">{{n}}</option></select>
    <label>한 묶음에 넣는 자막 수 (20~30)</label><input v-model="f.per_strip" type="number" min="5" max="40">
    <label>동시에 읽는 묶음 수</label><input v-model="f.workers" type="number" min="1" max="8">
    <label>자막 없음 기준 시간(초)</label><input v-model="f.min_gap" type="number" min="5" max="120">
    <label><input v-model="f.ai_tidy" type="checkbox"> 자막 읽기 뒤 AI가 문장 정리 (문장 묶기, 글자 교정, 읽는 글, 확인 필요 표시)</label>
    <label>음성 합성 품질</label>
    <select v-model="f.tts_steps"><option value="8">표준 (문장당 약 5초)</option><option value="4">빠름 (품질 조금 낮음, 약 2배 빠름)</option></select>
    <div class="muted">품질을 바꾸면 모든 문장의 음성을 다시 만듭니다.</div>
    <label>읽기 사전 (한 줄에 하나, 보이는 글=읽는 글)</label>
    <textarea v-model="f.dict" rows="6" placeholder="할렐루야=할렐루우야" style="width:100%"></textarea>
    <div class="row" style="justify-content:flex-end;margin-top:12px"><button @click="$emit('close')">닫기</button><button class="primary" @click="save">저장</button></div>
  </ModalCard>`,
};
