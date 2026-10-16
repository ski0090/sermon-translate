// 자동 진행 멈추기
import { stopBatch } from "../api/batch.js";

export default {
  emits: ["changed"],
  setup(_, { emit }) {
    async function stop() {
      if (!confirm("지금 하던 단계까지만 하고 멈춥니다.")) return;
      await stopBatch();
      emit("changed");
    }
    return { stop };
  },
  template: `<button class="small" @click="stop">멈추기</button>`,
};
