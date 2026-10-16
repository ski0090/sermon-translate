// 음성 영상 한 줄의 유튜브: 올렸으면 링크, 대기·올리는 중이면 진행과 취소, 완성된 영상이 있고 유튜브가 연결(yt)되어 있으면 올리기(실패 표시).
// 한 줄(.pright)에 그대로 늘어놓도록 감싸는 요소 없이 그린다. 끝나면 changed
import { svBusy } from "@/entities/sleep-video/index.js";
import { uploadSleep, cancelSleepUpload } from "../api/upload.js";

export default {
  props: ["x", "yt"],
  emits: ["changed"],
  setup(props, { emit }) {
    async function run(call) {
      try {
        await call(props.x);
      } catch (e) {
        alert(e.message);
      }
      emit("changed");
    }
    return {
      busy: svBusy,
      upload: () => run(uploadSleep),
      cancel: () => run(cancelSleepUpload),
    };
  },
  template: `<a v-if="(x.youtube||{}).status==='done'" :href="x.youtube.url" target="_blank">▶ 유튜브 (비공개)</a>
          <template v-else-if="x.youtube&&(x.youtube.status==='queued'||x.youtube.status==='uploading')"><span class="muted">{{x.youtube.msg||"유튜브 대기 중"}}{{x.youtube.progress?" "+Math.round(x.youtube.progress*100)+"%":""}}</span><button class="small" @click="cancel">취소</button></template>
          <template v-else-if="x.has_file&&!busy(x)&&yt"><span v-if="(x.youtube||{}).status==='error'" class="muted" style="color:var(--bad)" :title="x.youtube.error||''">유튜브 실패</span><button class="small" @click="upload">유튜브 올리기</button></template>`,
};
