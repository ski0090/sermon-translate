// 입력 칸(area면 여러 줄): 고치는 중에는 화면을 새로 그려도 덮지 않고, 놓으면(change) save로 알린다
import { ref, watch } from "vue";

export default {
  props: { value: null, area: Boolean },
  emits: ["save"],
  setup(props, { emit }) {
    const norm = (x) => (x == null ? "" : String(x));
    const v = ref(norm(props.value));
    let focused = false;
    watch(
      () => props.value,
      (x) => {
        if (!focused) v.value = norm(x);
      },
    );
    return {
      v,
      focus: () => {
        focused = true;
      },
      blur: () => {
        focused = false;
      },
      change: () => emit("save", v.value),
    };
  },
  template: `<textarea v-if="area" v-model="v" @focus="focus" @blur="blur" @change="change"></textarea><input v-else v-model="v" @focus="focus" @blur="blur" @change="change">`,
};
