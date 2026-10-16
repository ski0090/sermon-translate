// 고른 날(days)의 도구와 한도를 정하는 칸: 처음 고른 날의 값으로 채우고, "적용"·"기본값으로"로 저장하면 saved(새 스케줄),
// "고르기 취소"는 clear. 고른 날 카드 안에 그대로 늘어놓도록 감싸는 요소 없이 그린다
import { reactive, watch } from "vue";
import { TOOLS } from "@/entities/ai-tool/index.js";
import { dayLabel } from "@/entities/schedule/index.js";
import { saveSchedule } from "../api/schedule.js";

export default {
  props: ["d", "days"],
  emits: ["saved", "clear"],
  setup(props, { emit }) {
    const pick = reactive({ tool: "claude", five_hour: 50, seven_day: 50 });
    // 고른 날의 입력 칸은 처음 고른 날의 값으로 채운다
    watch(
      () => props.days[0],
      (k) => {
        if (!k || !props.d) return;
        const v = props.d.days[k] || props.d.default;
        Object.assign(pick, {
          tool: v.tool || props.d.tool || "claude",
          five_hour: v.five_hour,
          seven_day: v.seven_day,
        });
      },
      { immediate: true },
    );
    async function send(x) {
      const v = await saveSchedule({ days: x });
      if (v) emit("saved", v);
    }
    const apply = () =>
      send(
        Object.fromEntries(
          props.days.map((k) => [
            k,
            {
              tool: pick.tool,
              five_hour: pick.five_hour,
              seven_day: pick.seven_day,
            },
          ]),
        ),
      );
    const reset = () =>
      send(Object.fromEntries(props.days.map((k) => [k, null])));
    return { pick, apply, reset, label: dayLabel, TOOLS };
  },
  template: `<div class="row" style="margin:0"><strong>고른 날 {{days.length}}일</strong><span class="muted">{{days.slice(0,8).map(label).join(", ")}}{{days.length>8?" …":""}}</span></div>
        <div class="row">도구 <select v-model="pick.tool"><option v-for="(n,k) in TOOLS" :key="k" :value="k">{{n}}</option></select>
          <label>5시간 <input type="number" min="0" max="100" step="5" v-model.number="pick.five_hour" style="width:70px">%</label>
          <label>주간 <input type="number" min="0" max="100" step="5" v-model.number="pick.seven_day" style="width:70px">%</label>
          <button class="primary small" @click="apply">적용</button><button class="small" @click="reset">기본값으로</button><button class="small" @click="$emit('clear')">고르기 취소</button></div>`,
};
