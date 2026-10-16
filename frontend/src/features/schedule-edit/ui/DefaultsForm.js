// 기본 도구와 기본 한도(5시간·주간 %) 줄: 달력에서 정하지 않은 날에 쓴다. 고치는 중이면(dirty) 새로 받아도 덮지 않는다. 저장하면 saved(새 스케줄)
import { reactive, watch } from "vue";
import { TOOLS } from "@/entities/ai-tool/index.js";
import { saveSchedule } from "../api/schedule.js";

export default {
  props: ["d"],
  emits: ["saved"],
  setup(props, { emit }) {
    const def = reactive({
      tool: "claude",
      five_hour: 50,
      seven_day: 50,
      dirty: false,
    });
    watch(
      () => props.d,
      (v) => {
        if (!def.dirty)
          Object.assign(def, {
            tool: v.tool || "claude",
            five_hour: v.default.five_hour,
            seven_day: v.default.seven_day,
          });
      },
      { immediate: true },
    );
    async function saveDef() {
      const v = await saveSchedule({
        tool: def.tool,
        default: { five_hour: def.five_hour, seven_day: def.seven_day },
      });
      if (v) {
        def.dirty = false;
        emit("saved", v);
      }
    }
    return { def, saveDef, TOOLS };
  },
  template: `<div class="row" style="margin-top:10px">기본 도구 <select v-model="def.tool" @change="def.dirty=true"><option v-for="(n,k) in TOOLS" :key="k" :value="k">{{n}}</option></select>
        기본 한도 <label>5시간 <input type="number" min="0" max="100" step="5" v-model.number="def.five_hour" @input="def.dirty=true" style="width:70px">%</label>
        <label>주간 <input type="number" min="0" max="100" step="5" v-model.number="def.seven_day" @input="def.dirty=true" style="width:70px">%</label>
        <button class="small" @click="saveDef">기본값 저장</button><span class="muted">달력에서 정하지 않은 날에 씁니다.</span></div>`,
};
