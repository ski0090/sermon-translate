// 진행 줄(.job): 알림 글, 막대, 퍼센트. 뒤에 붙일 단추(중단 등)는 slot으로 받는다
import { computed } from "vue";

export default {
  props: { msg: String, progress: Number },
  setup(props) {
    return { pct: computed(() => Math.round(props.progress * 100)) };
  },
  template: `<div class="job"><span>{{msg}}</span><div class="bar"><i :style="{width:pct+'%'}"></i></div><span class="time">{{pct}}%</span><slot/></div>`,
};
