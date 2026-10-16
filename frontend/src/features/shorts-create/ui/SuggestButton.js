// "Claude로 후보 3개 만들기"(쇼츠가 있으면 "3개 더"). 고르는 중(busy)에는 누를 수 없다. 요청은 act로 넘긴다
import { suggestShorts } from "../api/create.js";

export default {
  props: { pid: String, more: Boolean, busy: Boolean },
  emits: ["act"],
  template: `<button class="primary small" :disabled="busy" @click="$emit('act',()=>suggest(pid))">{{more?"Claude로 후보 3개 더":"Claude로 후보 3개 만들기"}}</button>`,
  setup() {
    return { suggest: suggestShorts };
  },
};
