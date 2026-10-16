// 프로젝트 작업 화면(#/p/<프로젝트>): 왼쪽 영상, 오른쪽 단계 패널(자막 읽기 · 정리와 검수 · 음성 · 내보내기), 아래 타임라인(잘라내기 구간).
// 화면 전체가 함께 쓰는 상태와 동작(W)은 model/session.js에서 만들어 provideWork로 넘긴다. 단계 단추는 머리줄(#hdrSlot)로 옮겨 그린다
import { computed, onMounted, onUnmounted } from "vue";
import { provideWork } from "@/entities/project/index.js";
import { SettingsModal } from "@/features/project-settings/index.js";
import { JobProgress } from "@/features/job-cancel/index.js";
import { WorkVideo } from "@/widgets/work-video/index.js";
import { WorkTimeline } from "@/widgets/work-timeline/index.js";
import {
  StepTabs,
  ScanPanel,
  ReviewPanel,
  TtsPanel,
  ExportPanel,
} from "@/widgets/work-steps/index.js";
import { createWorkSession } from "../model/session.js";

export default {
  props: ["pid"],
  components: {
    ScanPanel,
    ReviewPanel,
    TtsPanel,
    ExportPanel,
    StepTabs,
    SettingsModal,
    JobProgress,
    WorkVideo,
    WorkTimeline,
  },
  setup(props) {
    const { W, open, close } = createWorkSession(props.pid);
    provideWork(W);
    const job = computed(() => W.d && W.d.job);
    const errText = computed(
      () =>
        W.err ||
        (job.value && job.value.error ? "작업 실패: " + job.value.error : ""),
    );
    const panel = computed(
      () =>
        ({
          scan: "ScanPanel",
          review: "ReviewPanel",
          tts: "TtsPanel",
          export: "ExportPanel",
        })[W.step],
    );
    onMounted(open);
    onUnmounted(close);
    return { W, errText, panel };
  },
  template: `<div v-if="!W.d" class="start"><div v-if="W.err" class="err">{{W.err}}</div><div v-else class="card muted">불러오는 중…</div></div>
  <section v-else class="work">
    <Teleport defer to="#hdrSlot">
      <StepTabs/>
      <button class="small" @click="W.settings=true">프로젝트 설정</button>
    </Teleport>
    <WorkVideo/>
    <div class="wright" @wheel.passive="W.onWheel">
      <JobProgress/>
      <div v-if="errText" class="err">{{errText}}</div>
      <div class="panel"><component :is="panel"/></div>
    </div>
    <WorkTimeline/>
    <SettingsModal v-if="W.settings" @close="W.settings=false"/>
  </section>`,
};
