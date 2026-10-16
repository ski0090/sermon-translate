// 한도 막대 하나: 쓴 비율(0~1), 초기화 시각, 덧붙임 말. 70% 넘으면 주황, 90% 넘으면 빨강
import { computed } from "vue";
import { when } from "@/shared/lib/index.js";

export default {
  props: ["label", "used", "resets", "note"],
  setup(props) {
    const p = computed(() => Math.round(props.used * 100));
    const color = computed(() =>
      p.value >= 90
        ? "var(--bad)"
        : p.value >= 70
          ? "var(--warn)"
          : "var(--accent)",
    );
    return { p, color, when };
  },
  template: `<div class="uvrow"><span class="uvlab">{{label}}</span>
    <span v-if="used==null" class="muted">모름</span>
    <template v-else><div class="uvbar"><i :style="{width:Math.min(100,p)+'%',background:color}"></i></div>
      <span class="uvval"><b>{{p}}%</b> 사용 · 남음 {{Math.max(0,100-p)}}%</span><span class="muted">{{resets?when(resets)+" 초기화":""}}{{note?" · "+note:""}}</span></template>
  </div>`,
};
