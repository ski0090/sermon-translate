// 정리와 검수 단계와, 음성 단계가 함께 쓰는 문장 목록.
// 문장마다 자막 그림과 읽은 글을 나란히 보고 고치고, 나누고 합치고, 확인 필요를 지운다. 고친 칸은 놓는 순간 저장한다
import { computed, inject, ref, watch } from "vue";
import { api } from "@/shared/api/index.js";
import { fmt } from "@/shared/lib/index.js";

export const edited = (s) => {
  const n = (t) => (t || "").replace(/[\s.,?!…"'“”‘’]/g, "");
  return !!s.ai && n(s.ai) !== n(s.raw);
};
// 글자 단위 LCS로 b에서 a와 다른 글자를 표시한 조각 [{t, m}]. 같은 쌍은 다시 계산하지 않는다
const diffCache = new Map();
function diffParts(a, b) {
  const key = a + "\u0000" + b;
  if (diffCache.has(key)) return diffCache.get(key);
  const n = a.length,
    m = b.length;
  let out;
  if (n * m > 40000) out = [{ t: b, m: false }];
  else {
    const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--)
      for (let j = m - 1; j >= 0; j--)
        dp[i][j] =
          a[i] === b[j]
            ? dp[i + 1][j + 1] + 1
            : Math.max(dp[i + 1][j], dp[i][j + 1]);
    out = [];
    const push = (c, mk) => {
      const l = out[out.length - 1];
      if (l && l.m === mk) l.t += c;
      else out.push({ t: c, m: mk });
    };
    let i = 0,
      j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        push(b[j], false);
        i++;
        j++;
      } else if (dp[i + 1][j] >= dp[i][j + 1]) i++;
      else {
        push(b[j], true);
        j++;
      }
    }
    while (j < m) push(b[j++], true);
  }
  diffCache.set(key, out);
  return out;
}

// 입력 칸: 고치는 중에는 화면을 새로 그려도 덮지 않고, 놓으면(change) save로 알린다
export const Edit = {
  props: { value: null, area: Boolean },
  emits: ["save"],
  setup(props, { emit }) {
    const norm = (x) => (x == null ? "" : String(x));
    const v = ref(norm(props.value));
    let focused = false;
    watch(
      () => props.value,
      (x) => {
        if (!focused) v.value = norm(x);
      },
    );
    return {
      v,
      focus: () => {
        focused = true;
      },
      blur: () => {
        focused = false;
      },
      change: () => emit("save", v.value),
    };
  },
  template: `<textarea v-if="area" v-model="v" @focus="focus" @blur="blur" @change="change"></textarea><input v-else v-model="v" @focus="focus" @blur="blur" @change="change">`,
};

const SentenceRow = {
  props: { s: Object, pl: Object, cur: Boolean, tts: Boolean },
  components: { Edit },
  setup(props) {
    const W = inject("W"),
      regen = ref(false);
    const isEdited = computed(() => edited(props.s));
    const diff = computed(() =>
      isEdited.value ? diffParts(props.s.ai, props.s.raw) : [],
    );
    const preview = computed(
      () => props.s.reading_auto || props.s.text.replace(/["'“”‘’]/g, ""),
    );
    const cap = (cid) => W.d.captions[cid];
    async function post(path, method, body) {
      try {
        await api(W.P(path), method, body);
      } catch (e) {
        alert(e.message);
      }
      await W.reload();
    }
    const sid = () => props.s.id;
    return {
      W,
      regen,
      isEdited,
      diff,
      preview,
      cap,
      fmt,
      save: (body) => post("/sentence/" + sid(), "POST", body),
      split: (cid) => post(`/sentence/${sid()}/split`, "POST", { cap: +cid }),
      merge: () => post(`/sentence/${sid()}/merge`, "POST", {}),
      del() {
        if (confirm("이 문장을 지울까요? 음성도 만들지 않습니다."))
          post("/sentence/" + sid(), "DELETE");
      },
      async regenerate() {
        regen.value = true;
        try {
          await api(W.P(`/sentence/${sid()}/tts`), "POST", {});
        } catch (e) {
          alert(e.message);
        }
        regen.value = false;
        await W.reload();
      },
    };
  },
  template: `<div class="sent" :class="{cur}" :id="'s'+s.id">
    <div class="crops">
      <div v-for="(cid,i) in s.caps" :key="cid" class="cap"><img loading="lazy" :src="W.P('/crop/'+cap(cid).crop)" :title="fmt(cap(cid).start)" @click="W.seek(cap(cid).start)"><button v-if="i>0" class="small" @click="split(cid)">여기서 나누기</button></div>
    </div>
    <div>
      <div class="row" style="margin:0 0 4px"><span class="time">{{fmt(s.start)}} – {{fmt(s.end)}}</span>
        <span v-if="s.check" class="badge warn">확인 필요</span>
        <span v-if="isEdited" class="badge">자동 수정됨</span>
        <span v-if="pl&&pl.fixed_overflow" class="badge bad">고정 지점 초과</span><span v-else-if="pl&&pl.overflow" class="badge warn">길이 초과</span>
        <span v-if="pl&&pl.tempo>1.001" class="badge">{{pl.tempo.toFixed(2)}}배속</span>
        <span style="flex:1"></span>
        <button class="small" @click="W.seek(s.start)">▶ 영상</button><button v-if="s.tts" class="small" @click="W.play(W.P('/tts/'+s.tts))">♪ 음성</button>
      </div>
      <Edit area :value="s.text" @save="v=>save({text:v.trim()})"/>
      <div v-if="s.check&&s.note" class="muted" style="font-size:12px">확인: {{s.note}} <button class="small" @click="save({check:false})">확인함</button></div>
      <div v-if="isEdited" class="diff muted" style="font-size:12px">읽은 글: <template v-for="p in diff"><mark v-if="p.m">{{p.t}}</mark><template v-else>{{p.t}}</template></template> <button class="small" @click="save({text:s.raw})">되돌리기</button></div>
      <div class="reading">읽는 글: <Edit :value="s.reading" :placeholder="preview" @save="v=>save({reading:v.trim()||null})"/></div>
      <div class="tools"><button class="small" @click="merge">다음 문장과 합치기</button><button class="small" @click="del">삭제</button>
        <template v-if="tts">
          <label class="muted">속도 <Edit type="number" step="0.05" min="0.8" max="1.5" style="width:70px" :value="s.speed" :placeholder="String(W.d.settings.speed)" @save="v=>save({speed:v?+v:null})"/></label>
          <label class="muted">앞 쉼(초) <Edit type="number" step="0.1" min="0" max="5" style="width:64px" :value="s.pause||0" @save="v=>save({pause:+v||0})"/></label>
          <button class="small" :disabled="regen" @click="regenerate">{{regen?"만드는 중…":"음성 다시 만들기"}}</button>
        </template>
      </div>
    </div>
  </div>`,
};

// 문장 목록. 지금 거르기(W.filter)에 맞는 문장만 보이고, 영상에서 지금 나오는 문장(W.cursent)을 표시한다
export const SentenceList = {
  props: { tts: Boolean },
  components: { SentenceRow },
  setup() {
    const W = inject("W");
    const pm = computed(() =>
      Object.fromEntries(W.plan.map((p) => [p.sid, p])),
    );
    const list = computed(() =>
      W.d.sentences.filter((s) => {
        const p = pm.value[s.id];
        if (W.filter === "check") return s.check;
        if (W.filter === "ai") return edited(s);
        if (W.filter === "over") return p && (p.overflow || p.fixed_overflow);
        return true;
      }),
    );
    return { W, pm, list };
  },
  template: `<div><SentenceRow v-for="s in list" :key="s.id" :s="s" :pl="pm[s.id]" :cur="s.id===W.cursent" :tts="tts"/><p v-if="!list.length" class="muted">해당하는 문장이 없습니다.</p></div>`,
};

export default {
  components: { SentenceList },
  setup() {
    const W = inject("W");
    const counts = computed(() => ({
      check: W.d.sentences.filter((s) => s.check).length,
      ai: W.d.sentences.filter(edited).length,
      over: W.plan.filter((p) => p.overflow || p.fixed_overflow).length,
    }));
    const running = computed(() => !!(W.d.job && W.d.job.running));
    function tidy() {
      if (
        confirm(
          "문장 목록을 AI로 새로 만듭니다. 직접 고친 내용은 사라집니다. 계속할까요?",
        )
      )
        W.startJob("tidy");
    }
    return { W, counts, running, tidy };
  },
  template: `<div>
    <h2>정리와 검수</h2>
    <div class="row"><select v-model="W.filter"><option value="all">전체 ({{W.d.sentences.length}})</option><option value="check">확인 필요 ({{counts.check}})</option><option value="ai">자동 수정됨 ({{counts.ai}})</option><option value="over">길이 초과 ({{counts.over}})</option></select>
      <button class="small" :disabled="running" @click="tidy">AI로 다시 정리</button>
      <span class="muted">글을 고치면 그 문장의 음성은 다시 만듭니다. 그림 위의 <kbd>여기서 나누기</kbd>로 문장을 나눕니다.</span>
      <span style="flex:1"></span><button class="primary" @click="W.go('tts')">음성 만들기로</button></div>
    <SentenceList/>
  </div>`,
};
