// 사용량 "확인": 그 도구(tool)에 아주 짧게 물어 지금 한도를 읽는다(묻는 동안 "확인 중…"). 끝나면 checked
import { ref } from "vue";
import { checkUsage } from "../api/check.js";

export default {
  props: ["tool"],
  emits: ["checked"],
  setup(props, { emit }) {
    const busy = ref(false);
    async function check() {
      busy.value = true;
      try {
        await checkUsage(props.tool);
      } catch (e) {
        alert(e.message);
      }
      busy.value = false;
      emit("checked");
    }
    return { busy, check };
  },
  template: `<button class="small" :disabled="busy" @click="check">{{busy?"확인 중…":"확인"}}</button>`,
};
