// 드라이브 영상 한 줄의 유튜브 상태: 올리기 버튼, 대기·진행, 링크, 실패
import { computed } from "vue";
import { youtubeConnected, privacyName } from "@/entities/youtube/index.js";
import { uploadToYoutube, cancelYoutubeUpload } from "../api/upload.js";

export default {
  props: ["it"],
  emits: ["changed"],
  setup(props, { emit }) {
    const y = computed(() => props.it.youtube || {}),
      ex = computed(() => props.it.yt_existing);
    const connected = youtubeConnected;
    const show = computed(
      () =>
        ["done", "queued", "uploading", "error"].includes(y.value.status) ||
        !!ex.value ||
        (props.it.yt_ready && connected.value),
    );
    const caps = computed(
      () =>
        ({ none: " · 자막 파일 없음", existing: " · 자막은 원래 있던 것" })[
          y.value.captions
        ] || "",
    );
    async function act(a) {
      try {
        await (a === "cancel" ? cancelYoutubeUpload : uploadToYoutube)(
          props.it.path,
        );
      } catch (e) {
        alert(e.message);
      }
      emit("changed");
    }
    return { y, ex, connected, show, caps, priv: privacyName, act };
  },
  template: `<div v-if="show" class="muted" style="text-align:right;margin-top:2px">
    <template v-if="y.status==='done'"><a :href="y.url" target="_blank" @click.stop>▶ 유튜브 ({{priv(y.privacy)}}{{y.existing?" · 이미 있던 영상":""}})</a>{{caps}}</template>
    <template v-else-if="y.status==='queued'||y.status==='uploading'"><span>{{y.msg||"유튜브 대기 중"}}{{y.status==='uploading'&&y.progress?" "+Math.round(y.progress*100)+"%":""}}{{y.resumed?" · 서버가 다시 켜져 처음부터 다시 올리는 중":""}}</span> <button class="small" @click.stop="act('cancel')">취소</button></template>
    <template v-else-if="y.status==='error'"><span style="color:var(--bad)">유튜브 실패: {{y.error}}</span> <button class="small" @click.stop="act('upload')">다시 하기</button></template>
    <template v-else-if="ex"><a :href="ex.url" target="_blank" @click.stop>▶ 유튜브 (이미 있음 · {{priv(ex.privacy)}})</a> <button v-if="connected" class="small" @click.stop="act('upload')">재생목록·자막 넣기</button></template>
    <button v-else class="small" @click.stop="act('upload')">{{y.video_id?"유튜브 올리기 이어서":"유튜브 올리기"}}</button>
  </div>`,
};
