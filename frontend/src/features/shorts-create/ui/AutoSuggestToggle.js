// "내보내기가 끝나면 자동으로 후보 3개 만들기" 켜고 끄기(지금 값 auto는 목록을 받을 때 함께 온다)
import { setAutoSuggest } from "../api/create.js";

export default {
  props: { auto: Boolean },
  setup() {
    return { setAuto: setAutoSuggest };
  },
  template: `<label class="muted" style="display:block;margin-top:8px"><input type="checkbox" :checked="auto" @change="setAuto($event.target.checked)"> 내보내기가 끝나면 자동으로 후보 3개 만들기</label>`,
};
