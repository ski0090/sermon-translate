// "아직 없는 영상 모두 만들기 (n편)": 음성 영상이 없는 영상(todo편)을 모두 대기열에 넣는다. 끝나면 changed
import { renderAllSleep } from "../api/render.js";

export default {
  props: { todo: Number },
  emits: ["changed"],
  setup(props, { emit }) {
    async function makeAll() {
      if (
        !confirm(
          `음성 영상이 없는 ${props.todo}편을 모두 대기열에 넣습니다. 한 편에 약 11분 걸립니다.`,
        )
      )
        return;
      try {
        await renderAllSleep();
      } catch (e) {
        alert(e.message);
      }
      emit("changed");
    }
    return { makeAll };
  },
  template: `<button class="primary small" :disabled="!todo" @click="makeAll">아직 없는 영상 모두 만들기 ({{todo}}편)</button>`,
};
