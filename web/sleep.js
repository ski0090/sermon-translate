// 음성 영상(자면서 듣는 설교) 화면: 음성을 만든 영상마다 이퀄라이저 화면 + 싱크 없이 이은 음성 영상을 만들고,
// 재생·내려받기·유튜브 올리기를 한다. 메뉴에서 고른 상태만 보이고, 3초마다 새로 받아도 재생 중인 영상은 끊기지 않는다
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
} from "./vendor/vue.esm-browser.prod.js";
import { api, store, every, fmt, when, svStage } from "./lib.js";

const P = (x, p) => `/api/p/${encodeURIComponent(x.dir)}/sleep${p}`;

export default {
  setup() {
    const open = ref(null);
    const load = async () => {
      store.sleep = await api("/api/sleep");
    };
    let stop;
    onMounted(() => {
      stop = every(3000, load);
    });
    onUnmounted(() => stop());
    const d = computed(() => store.sleep);
    const items = computed(() =>
      d.value
        ? d.value.items.filter(
            (x) =>
              store.route.filter === "all" || svStage(x) === store.route.filter,
          )
        : [],
    );
    const todo = computed(() =>
      d.value
        ? d.value.items.filter((x) => !x.has_file && svStage(x) !== "making")
            .length
        : 0,
    );
    const busy = (x) => x.status === "queued" || x.status === "rendering";
    const pct = (x) => Math.round((x.progress || 0) * 100);
    const info = (x) =>
      (x.length ? fmt(x.length) + " · " : "") +
      (x.size ? Math.round(x.size / 2 ** 20) + "MB · " : "") +
      (x.rendered ? when(x.rendered) : "") +
      (x.drive && x.drive.folder
        ? " · 드라이브에 올림"
        : x.drive && x.drive.error
          ? " · 드라이브 실패"
          : "");
    async function act(x, a) {
      if (
        a === "cancel" &&
        x.status === "rendering" &&
        !confirm("만들던 음성 영상을 멈출까요?")
      )
        return;
      if (
        a === "" &&
        x.has_file &&
        !confirm("음성 영상을 다시 만듭니다. 약 11분 걸립니다.")
      )
        return;
      try {
        await api(P(x, a ? "/" + a : ""), "POST", {});
      } catch (e) {
        alert(e.message);
      }
      load();
    }
    async function makeAll() {
      if (
        !confirm(
          `음성 영상이 없는 ${todo.value}편을 모두 대기열에 넣습니다. 한 편에 약 11분 걸립니다.`,
        )
      )
        return;
      try {
        await api("/api/sleep", "POST", { action: "all" });
      } catch (e) {
        alert(e.message);
      }
      load();
    }
    return {
      open,
      d,
      items,
      todo,
      busy,
      pct,
      info,
      act,
      makeAll,
      P,
      setAuto: (v) => api("/api/sleep", "POST", { auto: v }),
    };
  },
  template: `<section class="sleepv">
    <div v-if="!d" class="card muted">불러오는 중…</div>
    <template v-else>
    <div class="card">
      <div class="row" style="justify-content:space-between;margin:0"><strong>음성 영상 (자면서 듣는 설교)</strong>
        <button class="primary small" :disabled="!todo" @click="makeAll">아직 없는 영상 모두 만들기 ({{todo}}편)</button></div>
      <div class="muted">원본 화면 대신 어두운 배경에 설교 제목과 소리에 맞춰 움직이는 이퀄라이저를 보여 주고, 소리는 영상 싱크 없이 문장을 원래 속도로 이은 더빙 음성입니다. 한 편씩 만들며 1시간 설교에 약 11분 걸립니다. 다 만들면 구글 드라이브의 결과 폴더에 올립니다.</div>
      <label class="muted" style="display:block;margin-top:8px"><input type="checkbox" :checked="d.auto" @change="setAuto($event.target.checked)"> 내보내기가 끝나면 자동으로 만들기</label>
    </div>
    <div class="card" style="margin-top:16px"><ul class="plist">
      <li v-for="x in items" :key="x.dir">
        <div class="pleft">
          <div>{{x.name}}
            <template v-if="x.status==='rendering'"><span class="badge ok">만드는 중</span> <span class="muted">{{x.msg||""}}</span></template>
            <span v-else-if="x.status==='queued'" class="badge">대기{{x.ahead?" (앞에 "+x.ahead+"편)":""}}</span>
            <template v-else-if="x.status==='error'"><span class="badge bad">실패</span> <span class="muted" style="color:var(--bad)">{{(x.error||"").slice(0,150)}}</span></template>
            <template v-else-if="x.has_file"><span class="badge ok">완성</span> <span class="muted">{{info(x)}}</span></template>
            <span v-else class="badge">아직 없음</span>
            <span v-if="!x.voice_done" class="badge warn" title="음성이 없는 문장은 빠집니다">음성 {{x.tts}}/{{x.sentences}}</span>
          </div>
          <div v-if="x.status==='rendering'" class="pjob" style="justify-content:flex-start;margin-top:4px"><div class="bar"><i :style="{width:pct(x)+'%'}"></i></div><span class="time">{{pct(x)}}%</span></div>
        </div>
        <div class="pright row" style="margin:0;justify-content:flex-end">
          <button v-if="busy(x)" class="small" @click="act(x,'cancel')">{{x.status==="rendering"?"중단":"대기 취소"}}</button>
          <button v-else class="small" :class="{primary:!x.has_file}" @click="act(x,'')">{{x.has_file?"다시 만들기":"만들기"}}</button>
          <template v-if="x.has_file"><button class="small" @click="open=open===x.dir?null:x.dir">{{open===x.dir?"닫기":"▶ 재생"}}</button><a :href="P(x,'/video?dl=1')" download>내려받기</a></template>
          <a v-if="(x.youtube||{}).status==='done'" :href="x.youtube.url" target="_blank">▶ 유튜브 (비공개)</a>
          <template v-else-if="x.youtube&&(x.youtube.status==='queued'||x.youtube.status==='uploading')"><span class="muted">{{x.youtube.msg||"유튜브 대기 중"}}{{x.youtube.progress?" "+Math.round(x.youtube.progress*100)+"%":""}}</span><button class="small" @click="act(x,'youtube/cancel')">취소</button></template>
          <template v-else-if="x.has_file&&!busy(x)&&d.yt"><span v-if="(x.youtube||{}).status==='error'" class="muted" style="color:var(--bad)" :title="x.youtube.error||''">유튜브 실패</span><button class="small" @click="act(x,'youtube')">유튜브 올리기</button></template>
        </div>
        <div v-if="open===x.dir&&x.has_file" style="flex-basis:100%"><video controls preload="metadata" :src="P(x,'/video?v='+Math.round(x.rendered||0))"></video></div>
      </li>
      <li v-if="!items.length" class="muted">해당하는 영상이 없습니다.</li>
    </ul></div>
    </template>
  </section>`,
};
