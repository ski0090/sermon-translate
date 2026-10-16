// Fable 이어 하기 줄: 켜고 끄면 바로 저장하고, 추가 몫 한도(%)는 "저장"으로. 고치는 중이면(dirty) 새로 받아도 덮지 않는다. 저장하면 saved(새 스케줄)
import { reactive, watch } from "vue";
import { when } from "@/shared/lib/index.js";
import { usagePct } from "@/entities/schedule/index.js";
import { saveSchedule } from "../api/schedule.js";

export default {
  props: ["d"],
  emits: ["saved"],
  setup(props, { emit }) {
    const fb = reactive({ on: false, limit: 100, dirty: false });
    watch(
      () => props.d,
      (v) => {
        if (!fb.dirty)
          Object.assign(fb, { on: v.fable.on, limit: v.fable.limit });
      },
      { immediate: true },
    );
    async function saveFable() {
      const v = await saveSchedule({ fable: { on: fb.on, limit: fb.limit } });
      if (v) {
        fb.dirty = false;
        emit("saved", v);
      }
    }
    return { fb, saveFable, pct: usagePct, when };
  },
  template: `<div class="row" style="margin-top:4px"><label><input type="checkbox" v-model="fb.on" @change="saveFable"> 기본 사용량을 다 쓰면 Fable로 이어 하기</label>
        <label>Fable 추가 몫 한도 <input type="number" min="0" max="100" step="5" v-model.number="fb.limit" @input="fb.dirty=true" style="width:70px">%</label>
        <button class="small" @click="saveFable">저장</button>
        <span class="muted">Fable 추가 몫 지금 {{pct((d.usage.seven_day_overage_included||{}).utilization)}} 사용{{(d.usage.seven_day_overage_included||{}).resetsAt?" · "+when(d.usage.seven_day_overage_included.resetsAt)+" 초기화":""}}</span>
        <span v-if="d.fable_now" class="badge ok">지금 Fable로 작업 중</span></div>`,
};
