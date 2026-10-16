// 프로젝트 작업 화면 왼쪽: 영상과 재생 시각, 그리고 문장 음성을 들려주는 audio. 두 요소는 W.media에 붙여 W.seek·W.play가 쓴다.
// 영상 시각이 바뀌면 지금 문장(W.cursent)을 표시하고 목록을 그 문장으로 굴린다(휠로 직접 굴리는 중이면 두고, 길이 초과만 볼 때도 두고).
// 미리 듣기 중이면 잘라내기 구간을 건너뛰고 문장마다 만든 음성을 들려준다. Space로 재생/멈춤
import { nextTick, onMounted, onUnmounted, ref } from "vue";
import { fmt } from "@/shared/lib/index.js";
import { useWork } from "@/entities/project/index.js";

export default {
  setup() {
    const W = useWork(),
      video = ref(null),
      audio = ref(null);
    function onMeta() {
      if (video.value.currentTime < 0.1) video.value.currentTime = W.first;
    }
    function onTime() {
      const v = video.value,
        t = v.currentTime;
      W.cur = t;
      if (!W.d) return;
      // 미리 듣기 중에는 잘라내기 구간을 건너뛴다
      const cut = W.d.cuts.find((c) => t >= c.start && t < c.end - 0.05);
      if (cut && W.preview) {
        v.currentTime = cut.end;
        return;
      }
      const s = W.d.sentences.find((x) => t >= x.start && t < x.end);
      if (s && W.cursent !== s.id) {
        W.cursent = s.id;
        if (W.filter !== "over" && !W.userScrolling)
          nextTick(() => {
            const el = document.getElementById("s" + s.id);
            if (el) el.scrollIntoView({ block: "nearest" });
          });
        if (W.preview && s.tts) {
          const a = audio.value;
          a.src = W.P("/tts/" + s.tts);
          a.playbackRate = 1;
          a.play().catch(() => {});
        }
      }
    }
    const onKey = (e) => {
      if (
        e.code === "Space" &&
        video.value &&
        !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)
      ) {
        e.preventDefault();
        video.value.paused ? video.value.play() : video.value.pause();
      }
    };
    onMounted(() => {
      W.media.video = video.value;
      W.media.audio = audio.value;
      addEventListener("keydown", onKey);
    });
    onUnmounted(() => {
      W.media.video = W.media.audio = null;
      removeEventListener("keydown", onKey);
    });
    return { W, video, audio, onMeta, onTime, fmt };
  },
  template: `<div class="wleft">
      <video ref="video" controls preload="metadata" :src="W.P('/video')" @loadedmetadata="onMeta" @timeupdate="onTime"></video>
      <div class="row"><span class="time">{{fmt(W.cur)}} / {{fmt(W.d.info.duration)}}</span><span class="muted">문장을 누르면 그 시점으로 이동합니다. <kbd>Space</kbd> 재생/멈춤</span></div>
      <audio ref="audio"></audio>
    </div>`,
};
