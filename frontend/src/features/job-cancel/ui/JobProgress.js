// 프로젝트에서 돌고 있는 작업의 진행 줄과 중단 단추(끝났거나 실패한 작업은 보이지 않는다)
import { computed } from "vue";
import { TaskProgress } from "@/shared/ui/index.js";
import { cancelJob, jobMsg, useWork } from "@/entities/project/index.js";

export default {
  components: { TaskProgress },
  setup() {
    const W = useWork();
    const job = computed(() => W.d && W.d.job);
    const jobOn = computed(
      () => job.value && !job.value.done && !job.value.error,
    );
    return { job, jobOn, jobMsg, cancel: () => cancelJob(W.pid) };
  },
  template: `<TaskProgress v-if="jobOn" :msg="jobMsg(job)" :progress="job.progress"><button class="small" @click="cancel">중단</button></TaskProgress>`,
};
