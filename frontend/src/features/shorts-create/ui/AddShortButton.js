// "직접 추가": 원본 영상에서 쇼츠를 시작할 시각(분:초)을 물어 그 자리에 쇼츠를 만든다. 요청은 act로 넘긴다
import { addShort } from "../api/create.js";

export default {
  props: { pid: String },
  emits: ["act"],
  setup(props, { emit }) {
    function addNew() {
      const v = prompt(
        "원본 영상에서 쇼츠를 시작할 시각을 적으세요 (예: 12:30)",
      );
      if (!v) return;
      const at = v
        .trim()
        .split(":")
        .reduce((a, x) => a * 60 + Number(x), 0);
      if (!isFinite(at)) return alert("시각을 알아보지 못했습니다.");
      emit("act", () => addShort(props.pid, at));
    }
    return { addNew };
  },
  template: `<button class="small" @click="addNew">직접 추가</button>`,
};
