// 내보내기 단계: 만들 파일과 원음 처리를 고르고 내보낸 뒤, 만든 파일을 내려받는다. 다 만들면 구글 드라이브의 결과 폴더에 올라간다
import {
  computed,
  inject,
  reactive,
  ref,
} from "./vendor/vue.esm-browser.prod.js";
import { api, fmt } from "./lib.js";

export default {
  setup() {
    const W = inject("W"),
      d = computed(() => W.d);
    const want = reactive({ video: true, audio: true, srt: true, txt: true });
    const oa = ref(W.d.settings.orig_audio === "duck" ? "duck" : "remove");
    const running = computed(() => !!(d.value.job && d.value.job.running));
    const files = computed(() => W.exportFiles || d.value.last_export || []);
    const total = computed(
      () =>
        d.value.info.duration -
        d.value.cuts.reduce((a, c) => a + (c.end - c.start), 0),
    );
    const noTts = computed(
      () => d.value.sentences.filter((s) => !s.tts).length,
    );
    // 결과 폴더는 서버의 drive_folder와 같은 규칙(원본 영상 폴더 아래 "<이름> 한국어 더빙")
    const folder = computed(() => {
      const dr = d.value.drive;
      if (!dr) return null;
      const parts = dr.path.split("/");
      parts.pop();
      return (
        (dr.shared && parts.length ? "공유 문서함/" : "내 드라이브/") +
        parts.concat([d.value.name + " 한국어 더빙"]).join("/")
      );
    });
    function run() {
      api(W.P("/settings"), "POST", { orig_audio: oa.value }).catch(() => {});
      W.startJob("export", {
        want: Object.keys(want).filter((k) => want[k]),
        orig_audio: oa.value,
      });
    }
    return {
      W,
      d,
      want,
      oa,
      running,
      files,
      total,
      noTts,
      folder,
      run,
      fmt,
      base: (f) => f.split(/[\\/]/).pop(),
    };
  },
  template: `<div>
    <h2>내보내기</h2>
    <div class="card">
      <div class="row"><label><input type="checkbox" v-model="want.video"> 한국어 음성이 입혀진 영상</label><label><input type="checkbox" v-model="want.audio"> 한국어 음성만 담은 오디오 파일</label></div>
      <div class="row"><label><input type="checkbox" v-model="want.srt"> 한국어 자막 파일 (srt)</label><label><input type="checkbox" v-model="want.txt"> 자막 텍스트 파일</label></div>
      <div class="row"><span>원음 처리</span><label><input type="radio" value="remove" v-model="oa"> 원음 제거</label><label><input type="radio" value="duck" v-model="oa"> 원음 낮춰서 깔기</label></div>
      <div class="muted">잘라내기 {{d.cuts.length}}개 구간을 빼면 결과 영상 길이는 약 {{fmt(total)}}입니다. 음성이 없는 문장 {{noTts}}개는 빠집니다.<br>원음을 제거하면 오디오 파일은 영상 타이밍과 상관없이 문장을 원래 속도로 이어 붙입니다.</div>
      <div class="row"><span class="muted">저장 위치: {{folder?"구글 드라이브 "+folder:"구글 드라이브에서 불러온 영상이 아니어서 이 PC에만 저장됩니다"}}</span></div>
      <div class="row" style="margin-top:8px"><button class="primary" :disabled="running" @click="run">내보내기</button></div>
    </div>
    <div v-if="files.length" class="card" style="margin-top:12px"><strong>만들어진 파일</strong>
      <div v-if="d.drive_export" class="muted">구글 드라이브 {{(d.drive_export.shared?"공유 문서함/":"내 드라이브/")+d.drive_export.folder}}에 올렸습니다.</div>
      <div v-else-if="d.drive&&!running" class="err" style="margin:6px 0">구글 드라이브에 올리지 못했습니다. 내보내기를 다시 누르세요.</div>
      <ul class="files"><li v-for="f in files" :key="f"><a :href="W.P('/download?path='+encodeURIComponent(f))" download>{{base(f)}}</a></li></ul>
    </div>
  </div>`,
};
