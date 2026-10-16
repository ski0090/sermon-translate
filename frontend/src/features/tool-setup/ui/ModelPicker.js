// 모델 고르기 줄: 목록에서 고르거나(Claude가 아니면) 목록에 없는 이름을 적어 "모델 저장". 새로 읽어도 고르는 중인 칸은 덮지 않는다
import { computed, ref, watch } from "vue";
import { modelOptions } from "@/entities/ai-tool/index.js";
import { saveTool } from "../api/tools.js";

export default {
  props: ["x"],
  emits: ["reload"],
  setup(props, { emit }) {
    const sel = ref(props.x.model || ""),
      text = ref("");
    watch(
      () => props.x.model,
      (v) => {
        sel.value = v || "";
      },
    );
    const opts = computed(() => modelOptions(props.x));
    async function saveModel() {
      const model = text.value.trim() || sel.value;
      text.value = "";
      document.activeElement.blur();
      try {
        await saveTool({ tool: props.x.tool, model });
      } catch (e) {
        alert(e.message);
      }
      emit("reload");
    }
    return { sel, text, opts, saveModel };
  },
  template: `<div class="row">모델 <select v-model="sel"><option v-for="o in opts" :key="o.v" :value="o.v" :disabled="o.off">{{o.t}}</option></select>
        <input v-if="x.tool!=='claude'" v-model="text" placeholder="목록에 없으면 이름 입력" style="width:200px"><button class="small" @click="saveModel">모델 저장</button></div>`,
};
