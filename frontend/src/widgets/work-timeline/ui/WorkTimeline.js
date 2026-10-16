// 프로젝트 작업 화면 아래 타임라인: 문장, 자막 없음, 찬양 후보, 잘라내기, 길이 초과, 고른 구간, 지금 시각을 그린다.
// 누르면 그 시각으로 가고, 끌면 구간(W.sel)을 고른다. 고른 구간과 후보를 잘라내는 단추는 features/cut-edit
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { fmt } from "@/shared/lib/index.js";
import { useWork } from "@/entities/project/index.js";
import { CutActions } from "@/features/cut-edit/index.js";

export default {
  components: { CutActions },
  setup() {
    const W = useWork(),
      canvas = ref(null);
    function draw() {
      const tl = canvas.value;
      if (!tl || !W.d) return;
      const dpr = devicePixelRatio,
        Wd = tl.clientWidth || 800,
        H = 84;
      if (tl.width !== Wd * dpr) {
        tl.width = Wd * dpr;
        tl.height = H * dpr;
      }
      const ctx = tl.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, Wd, H);
      const d = W.d,
        D = d.info.duration,
        x = (t) => (t / D) * Wd;
      ctx.fillStyle = "#eceef2";
      ctx.fillRect(0, 0, Wd, H);
      d.ranges.gaps.forEach((g) => {
        ctx.fillStyle = "#c3c8d0";
        ctx.fillRect(x(g.start), 0, Math.max(1, x(g.end) - x(g.start)), H);
      });
      d.ranges.lyrics.forEach((g) => {
        ctx.fillStyle = "rgba(228,180,0,.55)";
        ctx.fillRect(x(g.start), 0, Math.max(1, x(g.end) - x(g.start)), H);
      });
      d.sentences.forEach((s) => {
        ctx.fillStyle = s.tts ? "#5b8def" : "#9db6f2";
        ctx.fillRect(
          x(s.start),
          26,
          Math.max(1, x(s.end) - x(s.start) - 0.5),
          32,
        );
      });
      const pm = Object.fromEntries(W.plan.map((p) => [p.sid, p]));
      d.sentences.forEach((s) => {
        const p = pm[s.id];
        if (p && (p.overflow || p.fixed_overflow)) {
          ctx.fillStyle = p.fixed_overflow ? "#b91c1c" : "#f59e0b";
          ctx.fillRect(x(s.start), 22, Math.max(2, x(s.end) - x(s.start)), 3);
        }
      });
      d.cuts.forEach((c) => {
        ctx.fillStyle = "rgba(214,69,93,.45)";
        ctx.fillRect(x(c.start), 0, Math.max(1, x(c.end) - x(c.start)), H);
        ctx.strokeStyle = "#d6455d";
        ctx.strokeRect(
          x(c.start) + 0.5,
          0.5,
          Math.max(1, x(c.end) - x(c.start)) - 1,
          H - 1,
        );
      });
      if (W.sel) {
        ctx.fillStyle = "rgba(245,158,11,.35)";
        ctx.fillRect(x(W.sel[0]), 0, Math.max(1, x(W.sel[1]) - x(W.sel[0])), H);
      }
      ctx.fillStyle = "#6b7280";
      ctx.font = "11px sans-serif";
      for (let m = 0; m < D; m += 300) {
        ctx.fillRect(x(m), H - 14, 1, 14);
        ctx.fillText(fmt(m), x(m) + 3, H - 3);
      }
      ctx.fillStyle = "#111";
      ctx.fillRect(x(W.cur || 0) - 1, 0, 2, H);
    }
    watch(() => [W.d, W.plan, W.sel, W.cur], draw, { flush: "post" });
    let dragStart = null,
      dragMoved = false;
    function tlDown(e) {
      dragStart = e.offsetX;
      dragMoved = false;
    }
    function tlMove(e) {
      if (dragStart === null || !W.d) return;
      const D = W.d.info.duration,
        Wd = canvas.value.clientWidth;
      if (Math.abs(e.offsetX - dragStart) > 3) dragMoved = true;
      if (!dragMoved) return;
      const a = (Math.min(dragStart, e.offsetX) / Wd) * D,
        b = (Math.max(dragStart, e.offsetX) / Wd) * D;
      W.sel = [Math.max(0, a), Math.min(D, b)];
    }
    function tlUp() {
      if (dragStart === null || !W.d) return;
      const D = W.d.info.duration,
        Wd = canvas.value.clientWidth;
      if (!dragMoved) {
        W.sel = null;
        W.seek((dragStart / Wd) * D);
      }
      dragStart = null;
    }
    const selInfo = computed(() =>
      W.sel
        ? `선택: ${fmt(W.sel[0])} – ${fmt(W.sel[1])} (${Math.round(W.sel[1] - W.sel[0])}초)`
        : "타임라인을 끌어서 구간을 선택하세요.",
    );
    // 프로젝트를 받은 뒤에 붙으므로 처음 한 번은 직접 그린다
    onMounted(() => {
      addEventListener("mouseup", tlUp);
      addEventListener("resize", draw);
      draw();
    });
    onUnmounted(() => {
      removeEventListener("mouseup", tlUp);
      removeEventListener("resize", draw);
    });
    return { canvas, tlDown, tlMove, selInfo };
  },
  template: `<div class="wbottom">
      <canvas ref="canvas" class="timeline" @mousedown="tlDown" @mousemove="tlMove"></canvas>
      <div class="tlbar">
        <span class="legend"><span><i style="background:#5b8def"></i>문장</span><span><i style="background:var(--cut)"></i>잘라내기</span><span><i style="background:var(--gap)"></i>자막 없음</span><span><i style="background:var(--lyric)"></i>찬양 후보</span><span><i style="background:#f59e0b"></i>선택</span></span>
        <span class="muted">{{selInfo}}</span>
        <CutActions/>
      </div>
    </div>`,
};
