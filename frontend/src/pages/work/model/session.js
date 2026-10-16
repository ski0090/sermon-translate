// 프로젝트 작업 화면 전체가 함께 쓰는 상태와 동작(W). 화면이 만들어 provideWork로 넘기고, 위젯·기능은 useWork()로 꺼낸다.
// d는 프로젝트, plan은 음성 계획, step·filter는 고른 단계와 문장 거르기, cur·cursent는 영상 시각과 지금 문장,
// sel은 타임라인에서 고른 구간, media는 work-video가 붙이는 영상·음성 요소다. 작업이 돌면 1초마다 진행을 받는다
import { markRaw, reactive } from "vue";
import { nav } from "@/shared/router/index.js";
import {
  fetchJob,
  fetchPlan,
  fetchProject,
  projectPath,
  requestJob,
} from "@/entities/project/index.js";

export function createWorkSession(pid) {
  const W = reactive({
    pid,
    d: null,
    plan: [],
    step: "scan",
    filter: "all",
    preview: false,
    first: 0,
    cur: 0,
    cursent: null,
    sel: null,
    err: null,
    exportFiles: null,
    settings: false,
    userScrolling: false,
    media: markRaw({ video: null, audio: null }),
    P: (path) => projectPath(pid, path),
  });
  let poll = null,
    polling = false,
    scrollTimer = null;

  async function reload() {
    const d = await fetchProject(pid);
    W.plan = d.sentences.some((s) => s.tts) ? await fetchPlan(pid) : [];
    W.d = d;
    W.err = null;
    nav.workName = d.name;
  }
  function stopPoll() {
    clearInterval(poll);
    poll = null;
  }
  function startPoll() {
    stopPoll();
    poll = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        const j = await fetchJob(pid);
        if (!W.d) return;
        W.d.job = j;
        if (!j || j.done) {
          stopPoll();
          await reload();
          if (j) onJobDone(j);
        }
      } catch (e) {
        // 대기열에서 뺀 경우(j 없음)도 멈춘다
      } finally {
        polling = false;
      }
    }, 1000);
  }
  // 자막 읽기가 끝나면 정리와 검수로, 내보내기가 끝나면 만든 파일을 보인다
  function onJobDone(j) {
    if (j.error || j.cancelled) return;
    if (j.kind === "read") W.step = "review";
    else if (j.kind === "export") {
      W.step = "export";
      W.exportFiles = j.result && j.result.files;
    }
  }
  Object.assign(W, {
    reload,
    async startJob(kind, params = {}) {
      try {
        await requestJob(pid, kind, params);
      } catch (e) {
        W.err = e.message;
        return;
      }
      await reload();
      startPoll();
    },
    seek(t) {
      const v = W.media.video;
      v.currentTime = t;
      v.play().catch(() => {});
    },
    videoTime: () => (W.media.video ? W.media.video.currentTime : 0),
    play(src) {
      const a = W.media.audio;
      a.src = src;
      a.play().catch(() => {});
      return a;
    },
    go(step) {
      W.step = step;
      W.preview = false;
      if (W.media.video) W.media.video.muted = false;
      if (step === "tts" && W.filter === "ai") W.filter = "all";
    },
    setPreview(on) {
      W.preview = on;
      W.media.video.muted = on;
      if (!on) W.media.audio.pause();
    },
    // 문장 목록을 휠로 굴리면 4초 동안은 지금 문장으로 저절로 굴리지 않는다
    onWheel() {
      W.userScrolling = true;
      clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        W.userScrolling = false;
      }, 4000);
    },
  });

  // 처음 열 때: 문장이 있으면 정리와 검수부터 연다(서버는 review 단계를 따로 적지 않는다). 영상은 첫 문장(없으면 첫 자막)에서 시작한다
  async function open() {
    try {
      await reload();
    } catch (e) {
      W.err = e.message;
      return;
    }
    const d = W.d;
    W.step =
      !d.step || d.step === "load"
        ? "scan"
        : d.step === "scan" && d.sentences.length
          ? "review"
          : d.step;
    W.first = (d.sentences[0] || d.captions[0] || {}).start || 0;
    W.cur = W.first;
    if (d.job && d.job.running) startPoll();
  }
  function close() {
    stopPoll();
    nav.workName = null;
  }
  return { W, open, close };
}
