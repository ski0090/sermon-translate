// 프로젝트 목록 화면: 새 프로젝트(구글 드라이브, 유튜브 연결), 자동 진행, 드라이브 영상 목록과 다른 프로젝트.
// 왼쪽 메뉴에서 고른 단계(store.route.filter)의 영상만 보이고, 목록은 2초마다 새로 받는다(바뀐 줄만 다시 그린다)
import {
  computed,
  onMounted,
  onUnmounted,
  reactive,
  ref,
} from "./vendor/vue.esm-browser.prod.js";
import {
  api,
  store,
  every,
  fmt,
  when,
  fsize,
  libState,
  projStage,
  stageName,
  progressText,
  jobName,
  jobMsg,
  openProject,
} from "./lib.js";

const JobBar = {
  props: ["job"],
  setup(props) {
    return {
      msg: computed(() => jobMsg(props.job)),
      pct: computed(() => Math.round(props.job.progress * 100)),
    };
  },
  template: `<div class="pjob"><span :title="msg">{{msg}}</span><div class="bar"><i :style="{width:pct+'%'}"></i></div><span class="time">{{pct}}%</span></div>`,
};

// 유튜브 상태: 올리기 버튼, 대기·진행, 링크, 실패
const YtCell = {
  props: ["it"],
  emits: ["changed"],
  setup(props, { emit }) {
    const y = computed(() => props.it.youtube || {}),
      ex = computed(() => props.it.yt_existing);
    const connected = computed(() => !!(store.yt && store.yt.connected));
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
    const priv = (p) =>
      ({ public: "공개", unlisted: "일부 공개", private: "비공개" })[p] ||
      "비공개";
    async function act(a) {
      try {
        await api("/api/youtube/" + a, "POST", { path: props.it.path });
      } catch (e) {
        alert(e.message);
      }
      emit("changed");
    }
    return { y, ex, connected, show, caps, priv, act };
  },
  template: `<div v-if="show" class="muted" style="text-align:right;margin-top:2px">
    <template v-if="y.status==='done'"><a :href="y.url" target="_blank" @click.stop>▶ 유튜브 ({{priv(y.privacy)}}{{y.existing?" · 이미 있던 영상":""}})</a>{{caps}}</template>
    <template v-else-if="y.status==='queued'||y.status==='uploading'"><span>{{y.msg||"유튜브 대기 중"}}{{y.status==='uploading'&&y.progress?" "+Math.round(y.progress*100)+"%":""}}{{y.resumed?" · 서버가 다시 켜져 처음부터 다시 올리는 중":""}}</span> <button class="small" @click.stop="act('cancel')">취소</button></template>
    <template v-else-if="y.status==='error'"><span style="color:var(--bad)">유튜브 실패: {{y.error}}</span> <button class="small" @click.stop="act('upload')">다시 하기</button></template>
    <template v-else-if="ex"><a :href="ex.url" target="_blank" @click.stop>▶ 유튜브 (이미 있음 · {{priv(ex.privacy)}})</a> <button v-if="connected" class="small" @click.stop="act('upload')">재생목록·자막 넣기</button></template>
    <button v-else class="small" @click.stop="act('upload')">{{y.video_id?"유튜브 올리기 이어서":"유튜브 올리기"}}</button>
  </div>`,
};

const VOICES = ["M1", "M2", "M3", "M4", "M5", "F1", "F2", "F3", "F4", "F5"];
const BatchBox = {
  props: ["b"],
  emits: ["changed"],
  setup(props, { emit }) {
    const picked = ref(null);
    const voice = computed({
      get: () => picked.value || props.b.voice,
      set: (v) => {
        picked.value = v;
      },
    });
    const n = (k) => (props.b.count || {})[k] || 0;
    const sum = computed(() => {
      const b = props.b;
      return b.total
        ? `완료 ${n("done")} / ${b.total}편 · 검수 대기 ${n("ready")} · 자막 대기 ${n("waiting")} · 음성 대기열 ${b.voice_waiting || 0}편 · 실패 ${n("error")}${n("skipped") ? ` · 같은 영상이라 건너뜀 ${n("skipped")}` : ""}`
        : "";
    });
    async function start() {
      if (!confirm("끝나지 않은 영상을 모두 차례로 진행합니다. 시작할까요?"))
        return;
      await api("/api/batch", "POST", { action: "start", voice: voice.value });
      emit("changed");
    }
    async function stop() {
      if (!confirm("지금 하던 단계까지만 하고 멈춥니다.")) return;
      await api("/api/batch", "POST", { action: "stop" });
      emit("changed");
    }
    return { VOICES, voice, sum, start, stop, when };
  },
  template: `<div class="card" style="margin-top:16px">
    <template v-if="b.on">
      <div class="row" style="justify-content:space-between;margin:0"><strong>자동 진행 중 <span class="badge ok">목소리 {{b.voice}}</span></strong><button class="small" @click="stop">멈추기</button></div>
      <div class="muted">{{sum}}</div>
      <div v-if="b.current.prep" class="muted">자막 읽기: <b>{{b.current.prep.name}}</b> {{b.current.prep.msg||""}}</div>
      <div v-for="v in b.current.voice||[]" :key="v.name" class="muted">음성·내보내기: <b>{{v.name}}</b> {{v.msg||""}}</div>
      <div v-if="b.wait_until" class="muted" style="color:var(--warn)">{{b.wait_reason||"Claude 사용량 한도로"}} 자막 읽기를 {{when(b.wait_until)}}까지 쉬는 중 (음성은 계속)</div>
    </template>
    <template v-else>
      <div class="row" style="justify-content:space-between;margin:0"><div><strong>자동 진행</strong><div class="muted">끝나지 않은 JP 영상을 번호순으로 자막 읽기와 문장 정리까지 진행합니다. 검수한 뒤 음성은 각 영상에서 "음성 만들기"를 눌러 시작합니다(음성 대기열에서 4편씩 만듭니다).</div></div>
        <span class="row" style="margin:0">목소리 <select v-model="voice"><option v-for="v in VOICES" :key="v">{{v}}</option></select><button class="primary" @click="start">{{b.total?"다시 시작":"시작"}}</button></span></div>
      <div v-if="sum" class="muted">{{sum}}</div>
      <div v-if="b.stopped_reason" class="err" style="margin:6px 0">{{b.stopped_reason}}</div>
    </template>
    <div v-if="b.errors.length" class="muted" style="color:var(--bad)"><div v-for="e in b.errors" :key="e.name">{{e.name}}: {{e.error}}</div></div>
    <details v-if="(b.skipped||[]).length" class="muted"><summary>같은 영상이라 건너뛴 {{b.skipped.length}}편 (드라이브의 제목을 확인하세요)</summary><div v-for="x in b.skipped" :key="x.name">{{x.name}} = {{x.same_as}}</div></details>
  </div>`,
};

// 유튜브 영상 설명과 해시태그. 미리 보기는 서버의 yt_meta와 같은 규칙(해시태그를 설명 끝에 붙인다)
const YtMeta = {
  emits: ["close"],
  setup(_, { emit }) {
    const f = reactive({
      description: "",
      hashtags: "",
      shorts_title: "",
      shorts_description: "",
      sleep_title: "",
      sleep_description: "",
    });
    onMounted(async () => {
      const m = await api("/api/youtube/settings");
      for (const k in f) f[k] = m[k] ?? "";
    });
    const preview = computed(() => {
      const tags = f.hashtags
        .split(/[\s,]+/)
        .map((t) => t.replace(/^#+/, ""))
        .filter(Boolean);
      return (
        f.description
          .split("{이름}")
          .join("218 선생이 아닌 구세주 예수")
          .trim() +
        (tags.length ? "\n\n" + tags.map((t) => "#" + t).join(" ") : "")
      );
    });
    async function save() {
      try {
        await api("/api/youtube/settings", "POST", { ...f });
        emit("close");
      } catch (e) {
        alert(e.message);
      }
    }
    return { f, preview, save };
  },
  template: `<div class="modal"><div class="card">
    <h2 style="margin-top:0">유튜브 영상 설명과 해시태그</h2>
    <label>설명 ({이름}은 영상 이름으로 바뀝니다)</label>
    <textarea v-model="f.description" rows="5" style="width:100%"></textarea>
    <label>해시태그 (띄어쓰기로 구분, 설명 끝에 붙고 태그로도 들어갑니다. 앞의 3개가 제목 위에 보입니다)</label>
    <input v-model="f.hashtags" style="width:100%">
    <label>미리 보기</label>
    <pre class="muted" style="white-space:pre-wrap;background:var(--bg);padding:8px;border-radius:6px;margin:0">{{preview}}</pre>
    <label>쇼츠 제목 ({제목}은 쇼츠 화면 위의 제목 두 줄, {이름}은 영상 이름)</label>
    <input v-model="f.shorts_title" style="width:100%">
    <label>쇼츠 설명 ({링크}는 유튜브에 올린 전체 영상 주소. 전체 영상이 아직 없으면 그 줄은 빠집니다. 해시태그는 #Shorts와 위의 해시태그가 붙습니다)</label>
    <textarea v-model="f.shorts_description" rows="3" style="width:100%"></textarea>
    <label>음성 영상 제목 ({이름}은 영상 이름)</label>
    <input v-model="f.sleep_title" style="width:100%">
    <label>음성 영상 설명 ({링크}는 유튜브에 올린 더빙 영상 주소. 없으면 그 줄은 빠집니다)</label>
    <textarea v-model="f.sleep_description" rows="3" style="width:100%"></textarea>
    <div class="muted" style="margin-top:6px">새로 올리는 영상에만 적용됩니다. 이미 유튜브에 있던 영상의 설명은 바꾸지 않습니다.</div>
    <div class="row" style="justify-content:flex-end;margin-top:12px"><button @click="$emit('close')">닫기</button><button class="primary" @click="save">저장</button></div>
  </div></div>`,
};

// 구글 드라이브에서 영상 고르기. 다 받으면 그 프로젝트를 연다. 보던 폴더는 다시 열어도 그대로다
const D = reactive({ path: "", shared: false });
const DriveModal = {
  emits: ["close"],
  setup(_, { emit }) {
    const s = reactive({ items: null, error: null, job: null });
    const running = computed(() => !!(s.job && !s.job.done));
    const crumbs = computed(() => {
      const parts = D.path ? D.path.split("/") : [];
      return [
        { name: D.shared ? "공유 문서함" : "내 드라이브", path: "" },
      ].concat(
        parts.map((n, i) => ({
          name: n,
          path: parts.slice(0, i + 1).join("/"),
        })),
      );
    });
    async function list(path) {
      D.path = path;
      s.items = null;
      s.error = null;
      try {
        const items = await api(
          `/api/drive/list?path=${encodeURIComponent(path)}&shared=${D.shared ? "1" : ""}`,
        );
        if (path === D.path) s.items = items;
      } catch (e) {
        if (path === D.path) s.error = e.message;
      }
    }
    let poll = null;
    function watchJob() {
      clearInterval(poll);
      const tick = async () => {
        const { job } = await api("/api/drive/status");
        s.job = job;
        if (!job || job.done) {
          clearInterval(poll);
          poll = null;
          if (job && job.done && !job.error && !job.cancelled && job.result) {
            emit("close");
            openProject(job.result.id);
          }
        }
      };
      tick();
      poll = setInterval(tick, 1000);
    }
    async function pick(it) {
      const p = (D.path ? D.path + "/" : "") + it.name;
      if (it.dir) return list(p);
      try {
        await api("/api/drive/import", "POST", {
          path: p,
          size: it.size,
          shared: D.shared,
        });
      } catch (e) {
        alert(e.message);
        return;
      }
      watchJob();
    }
    onMounted(async () => {
      list(D.path);
      const { job } = await api("/api/drive/status");
      if (job && !job.done) watchJob();
    });
    onUnmounted(() => clearInterval(poll));
    return {
      D,
      s,
      running,
      crumbs,
      list,
      pick,
      fsize,
      cancel: () => api("/api/drive/cancel", "POST", {}),
    };
  },
  template: `<div class="modal"><div class="card">
    <div class="row" style="justify-content:space-between;margin-top:0"><h2 style="margin:0">구글 드라이브에서 영상 선택</h2><label class="muted" style="margin:0"><input type="checkbox" v-model="D.shared" :disabled="running" @change="list('')"> 공유 문서함</label></div>
    <div class="row crumbs"><template v-for="(c,i) in crumbs" :key="c.path"><span v-if="i"> / </span><a @click="list(c.path)">{{c.name}}</a></template></div>
    <ul class="plist dlist" :class="{busy:running}">
      <li v-if="s.error" class="err">{{s.error}}</li>
      <li v-else-if="!s.items" class="muted">불러오는 중…</li>
      <li v-else-if="!s.items.length" class="muted">폴더나 영상 파일이 없습니다.</li>
      <template v-else><li v-for="it in s.items" :key="it.name" @click="pick(it)"><span>{{it.dir?"📁 ":"🎬 "}}{{it.name}}</span><span class="muted">{{it.dir?"":fsize(it.size)}}</span></li></template>
    </ul>
    <div v-if="running" class="job"><span>{{s.job.msg||"내려받는 중"}}</span><div class="bar"><i :style="{width:Math.round(s.job.progress*100)+'%'}"></i></div><span class="time">{{Math.round(s.job.progress*100)}}%</span><button class="small" @click="cancel">중단</button></div>
    <div v-else-if="s.job&&s.job.error" class="err">{{s.job.error}}</div>
    <div class="muted">고른 영상은 이 PC(dubber/projects/_drive)에 내려받은 뒤 프로젝트로 만듭니다. 이미 받은 영상은 다시 받지 않습니다.</div>
    <div class="row" style="justify-content:flex-end;margin-top:12px"><button @click="$emit('close')">닫기</button></div>
  </div></div>`,
};

export default {
  components: { JobBar, YtCell, BatchBox, YtMeta, DriveModal },
  setup() {
    const all = computed(() => store.route.filter === "all"),
      f = computed(() => store.route.filter);
    const batch = ref(null),
      drive = ref(null),
      modal = ref(null);
    const remote = !["127.0.0.1", "localhost"].includes(location.hostname);
    const auto = {
      waiting: "자동 대기",
      ready: "검수 대기 · 음성은 직접",
      skipped: "같은 영상이라 건너뜀",
    };
    const rows = computed(() =>
      store.lib
        ? store.lib.items
            .map((it) => ({ it, st: libState(it) }))
            .filter((r) => all.value || r.st.stage === f.value)
        : [],
    );
    const others = computed(() =>
      store.lib
        ? store.lib.others.filter((p) => all.value || projStage(p) === f.value)
        : [],
    );
    const sum = computed(() => {
      const lib = store.lib;
      if (!lib || !lib.items.length) return "";
      if (!all.value) return `${rows.value.length}개`;
      const n = (k) =>
        lib.items.filter((it) => libState(it).group === k).length;
      return `${lib.items.length}개 · 완료 ${n("done")} · 진행 중 ${n("run")} · 시작 전 ${n("todo")}`;
    });
    async function load(refresh) {
      const [lib, yt, b] = await Promise.all([
        api("/api/library" + (refresh ? "?refresh=1" : "")),
        api("/api/youtube/status").catch(() => store.yt),
        all.value ? api("/api/batch").catch(() => batch.value) : batch.value,
      ]);
      store.lib = lib;
      store.yt = yt;
      batch.value = b;
    }
    let stop;
    onMounted(() => {
      stop = every(2000, () => load());
      api("/api/drive/status")
        .then((s) => {
          drive.value = s;
        })
        .catch(() => {});
    });
    onUnmounted(() => stop());
    async function openItem(it) {
      if (it.project) return openProject(it.project.dir);
      if (it.importing) return;
      const note = it.drive_done
        ? "\n이미 구글 드라이브에 결과가 있습니다. 다시 만들면 덮어씁니다."
        : it.legacy
          ? "\n다른 PC에서 작업한 기록이 있지만 이어서 할 수는 없고 처음부터 시작합니다."
          : "";
      if (
        !confirm(
          `"${it.name}" 영상(${fsize(it.size)})을 내려받아 작업을 시작할까요?${note}`,
        )
      )
        return;
      try {
        await api("/api/drive/import", "POST", {
          path: it.path,
          size: it.size,
          shared: false,
        });
      } catch (e) {
        alert(e.message);
      }
      await load();
    }
    async function ytLogin() {
      const w = window.open("", "_blank");
      try {
        const { url } = await api("/api/youtube/login", "POST", {});
        w.location = url;
      } catch (e) {
        w.close();
        alert(e.message);
      }
    }
    return {
      store,
      all,
      f,
      rows,
      others,
      sum,
      batch,
      drive,
      modal,
      remote,
      auto,
      load,
      openItem,
      ytLogin,
      openProject,
      stageName,
      projStage,
      progressText,
      jobName,
      fmt,
    };
  },
  template: `<section class="start">
    <div v-if="all" class="card">
      <div class="row" style="justify-content:space-between">
        <div><strong>새 프로젝트</strong><div class="muted">{{drive&&!drive.available?"구글 드라이브가 연결되어 있지 않습니다. 서버 PC에서 rclone으로 gdrive를 연결한 뒤 다시 실행하세요(README의 구글 드라이브 연결).":"화면 아래쪽에 한국어 자막이 있는 설교 영상을 구글 드라이브에서 고르세요. 결과물은 영상과 같은 폴더 아래 \\"영상 이름 한국어 더빙\\" 폴더에 저장됩니다."}}</div></div>
        <button class="primary" :disabled="!(drive&&drive.available)" @click="modal='drive'">구글 드라이브에서 선택</button>
      </div>
      <div v-if="store.yt" class="row" style="margin-top:10px;border-top:1px solid var(--line);padding-top:10px">
        <template v-if="store.yt.connected"><span class="muted">유튜브: <b>{{store.yt.channel||"연결됨"}}</b> 채널에 비공개로 올리고 재생목록 "{{store.yt.playlist}}"에 넣습니다.</span><button class="small" @click="modal='ytmeta'">설명·해시태그</button><button class="small" @click="ytLogin">다시 연결</button></template>
        <template v-else><span class="muted">유튜브가 연결되어 있지 않습니다.{{remote?" 연결은 서버 PC의 브라우저에서 해야 합니다.":""}}{{store.yt.login.busy?" 로그인 창에서 계정과 채널을 고르세요.":""}}{{store.yt.login.error?" 오류: "+store.yt.login.error:""}}</span><button class="small" @click="ytLogin">유튜브 연결</button></template>
      </div>
    </div>
    <BatchBox v-if="all&&batch" :b="batch" @changed="load()"/>
    <div class="card" style="margin-top:16px">
      <div class="row" style="justify-content:space-between;margin:0"><strong>구글 드라이브 {{store.lib?store.lib.root:""}} 폴더{{all?"":" · "+stageName(f)}}</strong><span class="row" style="margin:0"><span class="muted">{{sum}}</span><button class="small" @click="load(true)">새로고침</button></span></div>
      <ul class="plist">
        <li v-if="store.lib&&store.lib.error" class="err">{{store.lib.error}}</li>
        <template v-else-if="rows.length">
          <li v-for="r in rows" :key="r.it.path" @click="openItem(r.it)">
            <div class="pleft"><div>{{r.it.name}} <span class="badge" :class="r.st.cls">{{r.st.label}}</span><template v-if="auto[r.it.batch]&&!(r.it.project&&r.it.project.job)"> <span class="badge">{{auto[r.it.batch]}}</span></template></div></div>
            <div class="pright"><JobBar v-if="r.st.job" :job="r.st.job"/><div v-else class="muted" style="text-align:right">{{r.st.text}}</div><YtCell :it="r.it" @changed="load()"/></div>
          </li>
        </template>
        <li v-else class="muted">{{!store.lib||store.lib.loading?"불러오는 중…":all?"영상이 없습니다.":"이 단계의 영상이 없습니다."}}</li>
      </ul>
      <div v-if="others.length" style="margin-top:16px"><strong>다른 프로젝트</strong>
        <ul class="plist">
          <li v-for="p in others" :key="p.dir" @click="openProject(p.dir)">
            <div class="pleft"><div>{{p.name}} <span class="badge" :class="{ok:p.job}">{{p.job?"진행 중 · "+jobName(p.job):p.exported?"완료":stageName(projStage(p))}}</span></div><div class="muted ellipsis">{{p.drive||p.video||""}}</div></div>
            <div class="pright"><JobBar v-if="p.job" :job="p.job"/><div v-else class="muted" style="text-align:right">{{progressText(p)}}</div><div class="muted" style="text-align:right">{{p.duration?fmt(p.duration):""}} · {{new Date(p.updated*1000).toLocaleString("ko-KR")}}</div></div>
          </li>
        </ul>
      </div>
    </div>
    <DriveModal v-if="modal==='drive'" @close="modal=null"/>
    <YtMeta v-if="modal==='ytmeta'" @close="modal=null"/>
  </section>`,
};
