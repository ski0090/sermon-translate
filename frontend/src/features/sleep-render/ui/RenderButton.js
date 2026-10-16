// 음성 영상 한 편: 만드는 중이면 "중단"(묻고), 대기 중이면 "대기 취소", 아니면 "만들기"·"다시 만들기"(약 11분이라 묻는다). 끝나면 changed
import { svBusy } from "@/entities/sleep-video/index.js";
import { renderSleep, cancelSleep } from "../api/render.js";

export default {
  props: ["x"],
  emits: ["changed"],
  setup(props, { emit }) {
    async function run(call) {
      try {
        await call(props.x);
      } catch (e) {
        alert(e.message);
      }
      emit("changed");
    }
    function cancel() {
      if (
        props.x.status === "rendering" &&
        !confirm("만들던 음성 영상을 멈출까요?")
      )
        return;
      run(cancelSleep);
    }
    function make() {
      if (
        props.x.has_file &&
        !confirm("음성 영상을 다시 만듭니다. 약 11분 걸립니다.")
      )
        return;
      run(renderSleep);
    }
    return { busy: svBusy, cancel, make };
  },
  template: `<button v-if="busy(x)" class="small" @click="cancel">{{x.status==="rendering"?"중단":"대기 취소"}}</button><button v-else class="small" :class="{primary:!x.has_file}" @click="make">{{x.has_file?"다시 만들기":"만들기"}}</button>`,
};
