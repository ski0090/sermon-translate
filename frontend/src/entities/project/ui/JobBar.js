// 목록 한 줄 오른쪽의 작은 진행 막대(.pjob): 작업 알림 글, 막대, 퍼센트
import { computed } from "vue";
import { jobMsg } from "../lib/job.js";

export default {
  props: ["job"],
  setup(props) {
    return {
      msg: computed(() => jobMsg(props.job)),
      pct: computed(() => Math.round(props.job.progress * 100)),
    };
  },
  template: `<div class="pjob"><span :title="msg">{{msg}}</span><div class="bar"><i :style="{width:pct+'%'}"></i></div><span class="time">{{pct}}%</span></div>`,
};
