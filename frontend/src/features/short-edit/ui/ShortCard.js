// 쇼츠 카드 하나: 왼쪽은 반영된 영상(없으면 지금 설정의 미리 보기 그림), 오른쪽은 제목, 구간(문장 단위), 가로 위치, 강조 구절,
// 만들기·내려받기·유튜브·삭제. 고치면 바로 저장되고 "다시 만들기"를 눌러야 영상에 반영된다. 몇 초마다 새로 받아도 고치는 중인 제목 칸은 그대로 둔다.
// 요청은 act(부르는 함수)로 넘기고, 받은 쇼츠 상태는 넘긴 쪽(shorts-editor)이 반영한다
import { computed, reactive, ref, watch } from "vue";
import { fmt } from "@/shared/lib/index.js";
import { shortsPath, previewVersion, marks } from "@/entities/shorts/index.js";
import { youtubeConnected } from "@/entities/youtube/index.js";
import { postShort, deleteShort } from "../api/short.js";

export default {
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
    const connected = youtubeConnected;
    const imgSrc = computed(() =>
      shortsPath(
        props.pid,
        `/${it.value.id}/frame?v=${previewVersion(it.value)}${pt.value != null ? "&t=" + pt.value.toFixed(2) : ""}`,
      ),
    );
    const videoSrc = computed(() =>
      shortsPath(
        props.pid,
        `/${it.value.id}/video?v=${Math.round(it.value.rendered || 0)}`,
      ),
    );
    const dlSrc = computed(() =>
      shortsPath(props.pid, `/${it.value.id}/video?dl=1`),
    );
    const post = (body, path = "") =>
      emit("act", () => postShort(props.pid, it.value.id, body, path));
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
      emit("act", () => deleteShort(props.pid, it.value.id));
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
