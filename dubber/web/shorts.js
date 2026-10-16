// 쇼츠 화면: 왼쪽은 쇼츠를 만들 수 있는 영상 목록(메뉴에서 고른 상태만), 오른쪽은 고른 영상의 쇼츠 카드.
// 카드에서 제목, 구간(문장 단위), 강조 구절, 가로 위치를 고치면 바로 저장되고, 미리 보기 그림으로 확인한 뒤
// "다시 만들기"를 누르면 영상에 반영된다. 몇 초마다 새로 받아도 고치는 중인 제목 칸과 고른 글은 그대로 둔다
import {
  computed,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
} from "./vendor/vue.esm-browser.prod.js";
import {
  api,
  store,
  every,
  fmt,
  shStage,
  SH_STAGES,
  openProject,
} from "./lib.js";

const SP = (pid, path) =>
  `/api/p/${encodeURIComponent(pid)}/shorts${path || ""}`;
// 미리 보기 그림 주소에 붙이는 값: 그림에 들어가는 설정이 바뀔 때만 바뀌어 그 카드의 그림만 새로 받는다
const hash = (s) => {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  return h.toString(36);
};
// 문장 하나를 강조 구절로 나눈 조각 [{text, mark, a, b}]
function marks(text, ph) {
  const f = new Array(text.length).fill(false);
  (ph || []).forEach((p) => {
    const i = text.indexOf(p);
    if (i >= 0) for (let k = i; k < i + p.length; k++) f[k] = true;
  });
  const out = [];
  let i = 0;
  while (i < text.length) {
    let j = i;
    while (j < text.length && f[j] === f[i]) j++;
    out.push({ text: text.slice(i, j), mark: f[i], a: i, b: j });
    i = j;
  }
  return out;
}

const ShortCard = {
  props: ["it", "sentences", "pid"],
  emits: ["act"],
  setup(props, { emit }) {
    const root = ref(null),
      video = ref(null),
      pt = ref(null);
    const title = reactive({ 0: "", 1: "" }),
      xpos = ref(50);
    let editing = false;
    watch(
      () => props.it.title,
      (v) => {
        if (!editing) {
          title[0] = v[0] || "";
          title[1] = v[1] || "";
        }
      },
      { immediate: true },
    );
    watch(
      () => props.it.xpos,
      (v) => {
        xpos.value = Math.round((v == null ? 0.5 : v) * 100);
      },
      { immediate: true },
    );
    const it = computed(() => props.it),
      y = computed(() => props.it.youtube || {});
    const seg = computed(() => {
      const ss = props.sentences;
      return {
        ss,
        a: ss.findIndex((s) => s.id === it.value.start),
        b: ss.findIndex((s) => s.id === it.value.end),
      };
    });
    // 왼쪽 칸: 고친 내용이 반영된 영상이 있으면 영상, 아니면 지금 설정의 미리 보기 그림
    const mode = computed(() =>
      it.value.has_file && !it.value.dirty
        ? "video"
        : it.value.invalid
          ? "none"
          : "img",
    );
    const busy = computed(() =>
      ["queued", "rendering"].includes(it.value.status),
    );
    const ytOk = computed(
      () => it.value.has_file && !it.value.dirty && !busy.value,
    );
    const connected = computed(() => !!(store.yt && store.yt.connected));
    const ver = computed(() =>
      hash(
        JSON.stringify([
          it.value.title,
          it.value.start,
          it.value.end,
          it.value.emph,
          it.value.xpos,
        ]),
      ),
    );
    const imgSrc = computed(() =>
      SP(
        props.pid,
        `/${it.value.id}/frame?v=${ver.value}${pt.value != null ? "&t=" + pt.value.toFixed(2) : ""}`,
      ),
    );
    const videoSrc = computed(() =>
      SP(
        props.pid,
        `/${it.value.id}/video?v=${Math.round(it.value.rendered || 0)}`,
      ),
    );
    const dlSrc = computed(() => SP(props.pid, `/${it.value.id}/video?dl=1`));
    const post = (body, path = "") =>
      emit("act", SP(props.pid, "/" + it.value.id + path), "POST", body);
    function move(k, dl) {
      const { ss, a, b } = seg.value,
        i = (k === "start" ? a : b) + dl;
      if (
        i < 0 ||
        i >= ss.length ||
        (k === "start" && i > b) ||
        (k === "end" && i < a)
      )
        return;
      post({ [k]: ss[i].id });
    }
    function unmark(s, p) {
      const emph = { ...it.value.emph };
      emph[s.id] = (emph[s.id] || []).filter((x) => {
        const i = s.text.indexOf(x);
        return i < 0 || i + x.length <= p.a || i >= p.b;
      });
      post({ emph });
    }
    function addEmph() {
      const sel = getSelection(),
        txt = sel.toString().replace(/\s+/g, " ").trim();
      const near = (n) => n && (n.nodeType === 1 ? n : n.parentElement),
        ea = near(sel.anchorNode),
        eb = near(sel.focusNode);
      const sa = ea && ea.closest(".shs"),
        sb = eb && eb.closest(".shs");
      if (!txt || !sa || sa !== sb || !root.value.contains(sa))
        return alert(
          "이 카드의 글에서 강조할 부분을 한 문장 안에서 마우스로 고른 뒤 누르세요.",
        );
      const s = props.sentences.find((x) => String(x.id) === sa.dataset.sid);
      if (!s.text.includes(txt))
        return alert("고른 글을 문장에서 찾지 못했습니다.");
      const emph = { ...it.value.emph };
      emph[s.id] = (emph[s.id] || []).concat([txt]);
      sel.removeAllRanges();
      post({ emph });
    }
    // 문장을 누르면 그 장면: 영상이면 그 시각으로, 그림이면 그 시각의 그림으로
    function seek(s) {
      if (it.value.invalid) return;
      const at = Math.max(0, s.t - it.value.at + Math.min(1, s.d / 2));
      if (video.value) {
        video.value.currentTime = at;
        video.value.play().catch(() => {});
      } else pt.value = at;
    }
    function del() {
      if (
        !confirm(
          `쇼츠 #${it.value.id}을(를) 지울까요? 이 PC의 영상 파일도 지웁니다(구글 드라이브와 유튜브에 올린 것은 그대로 둡니다).`,
        )
      )
        return;
      emit("act", SP(props.pid, "/" + it.value.id), "DELETE");
    }
    return {
      root,
      video,
      title,
      xpos,
      it,
      y,
      seg,
      mode,
      busy,
      ytOk,
      connected,
      imgSrc,
      videoSrc,
      dlSrc,
      post,
      move,
      unmark,
      addEmph,
      seek,
      del,
      marks,
      fmt,
      edit: (v) => {
        editing = v;
      },
      saveTitle: () => post({ title: [title[0], title[1]] }),
    };
  },
  template: `<div class="shcard" ref="root">
    <div class="shvid">
      <video v-if="mode==='video'" ref="video" controls preload="metadata" playsinline :src="videoSrc"></video>
      <div v-else-if="mode==='none'" style="padding:12px">{{it.invalid}}</div>
      <div v-else style="position:relative;width:100%;height:100%"><div class="shwait">미리 보기를 그리는 중…</div><img :key="imgSrc" class="shimg" alt="" :src="imgSrc" @error="$event.target.style.display='none'"></div>
    </div>
    <div class="shed">
      <div class="row"><b>#{{it.id}}</b>
        <span v-if="it.invalid" class="badge bad">{{it.invalid}}</span>
        <template v-else><span class="time" title="원본 영상에서의 시각">{{fmt(it.at)}} – {{fmt(it.at+it.len)}} · {{Math.round(it.len)}}초</span><span v-if="it.len>60" class="badge warn" title="쇼츠는 3분까지 올릴 수 있지만 짧을수록 좋습니다">60초 넘음</span></template>
        <template v-if="it.status==='rendering'"><span class="badge ok">만드는 중</span><span class="shbar"><i :style="{width:Math.round((it.progress||0)*100)+'%'}"></i></span><span class="muted">{{it.msg||""}}</span></template>
        <span v-else-if="it.status==='queued'" class="badge">만들기 대기{{it.ahead?" (앞에 "+it.ahead+"개)":""}}</span>
        <template v-else-if="it.status==='error'"><span class="badge bad">실패</span><span class="muted" style="color:var(--bad)">{{(it.error||"").slice(0,200)}}</span></template>
        <span v-else-if="it.has_file&&it.dirty" class="badge warn">고친 내용 반영 안 됨</span>
        <template v-else-if="it.has_file"><span class="badge ok">완성</span><span v-if="it.drive&&it.drive.folder" class="muted">드라이브에 올림</span><span v-else-if="it.drive&&it.drive.error" class="muted" style="color:var(--bad)" :title="it.drive.error">드라이브 올리기 실패</span></template>
        <span v-else class="badge">아직 안 만듦</span>
      </div>
      <div class="shtitle">
        <input v-model="title[0]" placeholder="제목 첫 줄 (흰색)" @focus="edit(true)" @blur="edit(false)" @change="saveTitle" @keydown.enter="$event.target.blur()">
        <input v-model="title[1]" placeholder="제목 둘째 줄 (노란색)" @focus="edit(true)" @blur="edit(false)" @change="saveTitle" @keydown.enter="$event.target.blur()">
      </div>
      <div class="row shrange"><span class="muted">시작</span><button class="small" title="앞 문장부터" @click="move('start',-1)">◀</button><button class="small" title="다음 문장부터" @click="move('start',1)">▶</button>
        <span class="muted" style="margin-left:8px">끝</span><button class="small" title="한 문장 덜" @click="move('end',-1)">◀</button><button class="small" title="한 문장 더" @click="move('end',1)">▶</button>
        <span class="muted" style="margin-left:8px">가로 위치</span><input type="range" min="0" max="100" step="5" v-model.number="xpos" :title="xpos+'%'" style="width:120px" @change="post({xpos:xpos/100})"></div>
      <div class="shtext">
        <span v-if="seg.a<0||seg.b<0" class="muted">문장을 찾지 못했습니다</span>
        <template v-else>
          <span v-if="seg.ss[seg.a-1]" class="ctx">앞 문장: {{seg.ss[seg.a-1].text}}</span>
          <span v-for="s in seg.ss.slice(seg.a,seg.b+1)" :key="s.id" class="shs" :data-sid="s.id" @click="seek(s)"><template v-for="p in marks(s.text,(it.emph||{})[s.id])"><mark v-if="p.mark" title="누르면 강조를 뺍니다" @click.stop="unmark(s,p)">{{p.text}}</mark><template v-else>{{p.text}}</template></template></span>
          <span v-if="seg.ss[seg.b+1]" class="ctx">다음 문장: {{seg.ss[seg.b+1].text}}</span>
        </template>
      </div>
      <div class="row"><button class="small" @mousedown.prevent @click="addEmph">선택한 글 강조</button><span class="muted">{{it.reason||""}}</span></div>
      <div class="row">
        <button class="small" :class="{primary:!it.has_file||it.dirty}" :disabled="busy||!!it.invalid" @click="post({},'/render')">{{it.has_file?"다시 만들기":"만들기"}}</button>
        <a v-if="it.has_file" :href="dlSrc" download>내려받기</a>
        <a v-if="y.status==='done'" :href="y.url" target="_blank">▶ 유튜브 쇼츠 (비공개)</a>
        <template v-else-if="y.status==='queued'||y.status==='uploading'"><span class="muted">{{y.msg||"유튜브 대기 중"}}{{y.status==='uploading'&&y.progress?" "+Math.round(y.progress*100)+"%":""}}</span><button class="small" @click="post({},'/youtube/cancel')">취소</button></template>
        <template v-else>
          <span v-if="y.status==='error'" class="muted" style="color:var(--bad)" :title="y.error||''">유튜브 실패: {{(y.error||"").slice(0,80)}}</span>
          <button v-if="connected" class="small" :disabled="!ytOk" :title="ytOk?'비공개로 올립니다':'영상을 만든 뒤 올릴 수 있습니다'" @click="post({},'/youtube')">{{y.status==='error'?"유튜브 다시 올리기":"유튜브 올리기"}}</button>
        </template>
        <span style="flex:1"></span><button class="small" @click="del">삭제</button>
      </div>
    </div>
  </div>`,
};

// 고른 영상의 쇼츠. 처음에 문장까지 받고, 그 뒤로는 2.5초마다 문장 없이 상태만 받는다
const ShortsDetail = {
  props: ["pid"],
  components: { ShortCard },
  setup(props) {
    const d = ref(null),
      err = ref(null);
    const take = (v) => {
      d.value = { ...v, sentences: d.value.sentences };
    };
    let stop;
    onMounted(async () => {
      try {
        d.value = await api(SP(props.pid));
      } catch (e) {
        err.value = e.message;
        return;
      }
      stop = every(2500, async () => take(await api(SP(props.pid, "?lite=1"))));
    });
    onUnmounted(() => stop && stop());
    async function act(url, method, body) {
      try {
        take(await api(url, method, body));
      } catch (e) {
        alert(e.message);
      }
    }
    const g = computed(() => (d.value && d.value.suggest) || {});
    function addNew() {
      const v = prompt(
        "원본 영상에서 쇼츠를 시작할 시각을 적으세요 (예: 12:30)",
      );
      if (!v) return;
      const at = v
        .trim()
        .split(":")
        .reduce((a, x) => a * 60 + Number(x), 0);
      if (!isFinite(at)) return alert("시각을 알아보지 못했습니다.");
      act(SP(props.pid, "/new"), "POST", { at });
    }
    return {
      d,
      err,
      g,
      act,
      addNew,
      suggest: () => act(SP(props.pid, "/suggest"), "POST", {}),
      open: () => openProject(props.pid),
    };
  },
  template: `<div v-if="err" class="err">{{err}}</div>
    <div v-else-if="!d" class="card muted">불러오는 중…</div>
    <template v-else>
      <div class="card" style="margin-bottom:12px">
        <div class="row" style="justify-content:space-between">
          <div><strong>{{d.name}}</strong> <span class="muted">{{d.items.length?"쇼츠 "+d.items.length+"개":""}}</span></div>
          <span class="row"><button class="small" @click="open">프로젝트 열기</button><button class="small" @click="addNew">직접 추가</button>
            <button class="primary small" :disabled="g.status==='queued'||g.status==='running'" @click="suggest">{{d.items.length?"Claude로 후보 3개 더":"Claude로 후보 3개 만들기"}}</button></span>
        </div>
        <div class="muted">제목과 구간, 강조를 고치면 왼쪽에 미리 보기 그림이 나오고, "다시 만들기"를 눌러야 영상에 반영됩니다. 강조는 글을 마우스로 고른 뒤 "선택한 글 강조"를 누르고, 노란 글을 누르면 뺍니다. 문장을 누르면 그 장면을 봅니다.</div>
        <div v-if="g.status==='running'" class="job" style="margin:8px 0 0"><span>{{g.msg||"Claude가 고르는 중"}}</span></div>
        <div v-else-if="g.status==='queued'" class="muted" style="margin-top:6px">후보 고르기 대기 중{{g.ahead?" (앞에 "+g.ahead+"개)":""}}{{g.msg?" · "+g.msg:""}}</div>
        <div v-else-if="g.status==='error'" class="err" style="margin:8px 0 0">후보를 고르지 못했습니다: {{g.error}}</div>
      </div>
      <ShortCard v-for="it in d.items" :key="it.id" :it="it" :sentences="d.sentences" :pid="pid" @act="act"/>
      <div v-if="!d.items.length" class="card muted">아직 쇼츠가 없습니다. "Claude로 후보 만들기"를 누르거나 "직접 추가"로 구간을 정하세요.</div>
    </template>`,
};

export default {
  components: { ShortsDetail },
  setup() {
    const auto = ref(false);
    let stop;
    onMounted(() => {
      api("/api/youtube/status")
        .then((y) => {
          store.yt = y;
        })
        .catch(() => {});
      stop = every(5000, async () => {
        const r = await api("/api/shorts");
        store.shorts = r.items;
        auto.value = !!r.auto;
      });
    });
    onUnmounted(() => stop());
    const f = computed(() => store.route.filter);
    const items = computed(() =>
      (store.shorts || []).filter(
        (x) => f.value === "all" || shStage(x) === f.value,
      ),
    );
    const title = computed(() =>
      f.value === "all"
        ? "쇼츠"
        : "쇼츠 · " + SH_STAGES.find((x) => x[0] === f.value)[1],
    );
    const badge = (x) =>
      x.busy
        ? {
            cls: "ok",
            text:
              x.suggest === "queued" || x.suggest === "running"
                ? "후보 고르는 중"
                : "만드는 중",
          }
        : x.error
          ? { cls: "bad", text: "후보 고르기 실패" }
          : x.count
            ? {
                cls: "",
                text:
                  x.done +
                  "/" +
                  x.count +
                  "개 완성" +
                  (x.uploaded ? " · 유튜브 " + x.uploaded : ""),
              }
            : { cls: "", text: "아직 없음" };
    const pick = (dir) => {
      location.hash = "#/shorts/" + f.value + "/" + encodeURIComponent(dir);
    };
    return {
      store,
      auto,
      items,
      title,
      badge,
      pick,
      setAuto: (v) => api("/api/shorts", "POST", { auto: v }),
    };
  },
  template: `<section class="shorts">
    <div class="card side">
      <strong>{{title}}</strong>
      <div class="muted">문장 정리가 끝난 영상에서 AI가 쇼츠 구간(30~60초)과 제목·강조 구절을 고르고, 원본 음성에 한국어 자막을 크게 박은 세로 영상(1080×1920)을 만듭니다. 결과는 "한국어 더빙/쇼츠" 폴더와 구글 드라이브에 저장됩니다.</div>
      <label class="muted" style="display:block;margin-top:8px"><input type="checkbox" :checked="auto" @change="setAuto($event.target.checked)"> 내보내기가 끝나면 자동으로 후보 3개 만들기</label>
      <ul class="plist">
        <li v-for="x in items" :key="x.dir" :class="{sel:x.dir===store.route.pid}" @click="pick(x.dir)"><div>{{x.name}}</div><span class="badge" :class="badge(x).cls">{{badge(x).text}}</span></li>
        <li v-if="!items.length" class="muted">{{!store.shorts?"불러오는 중…":store.shorts.length?"이 상태의 영상이 없습니다.":"문장 정리까지 끝난 영상이 없습니다."}}</li>
      </ul>
    </div>
    <div><ShortsDetail v-if="store.route.pid" :key="store.route.pid" :pid="store.route.pid"/><div v-else class="card muted">왼쪽에서 영상을 고르세요.</div></div>
  </section>`,
};
