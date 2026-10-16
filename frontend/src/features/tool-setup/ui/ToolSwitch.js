// 도구 "사용" 켜고 끄기(설치되지 않은 도구는 바꿀 수 없다). 끝나면 reload
import { saveTool } from "../api/tools.js";

export default {
  props: ["x"],
  emits: ["reload"],
  setup(props, { emit }) {
    async function setEnabled(on) {
      try {
        await saveTool({ tool: props.x.tool, enabled: on });
      } catch (e) {
        alert(e.message);
      }
      emit("reload");
    }
    return { setEnabled };
  },
  template: `<label class="row" style="margin:0"><input type="checkbox" :checked="x.enabled" :disabled="!x.installed" @change="setEnabled($event.target.checked)"> 사용</label>`,
};
