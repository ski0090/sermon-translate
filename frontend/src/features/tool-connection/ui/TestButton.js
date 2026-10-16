// "연결 시험": 도구를 아주 짧게 불러 본다(도는 동안 "시험 중…"). 끝나면 상태를 새로 확인한다
import { ref } from "vue";
import { runToolAction } from "../model/run.js";

export default {
  props: ["x"],
  emits: ["reload"],
  setup(props, { emit }) {
    const testing = ref(false);
    async function test() {
      testing.value = true;
      await runToolAction(emit, props.x.tool, "test", true);
      testing.value = false;
    }
    return { testing, test };
  },
  template: `<button class="small" :disabled="testing" @click="test">{{testing?"시험 중…":"연결 시험"}}</button>`,
};
