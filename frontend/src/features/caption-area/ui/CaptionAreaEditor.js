// 자막 영역(빨간 상자) 편집 카드: 영상 장면 위에 상자를 보이고, 끌어서 옮기거나 크기를 바꾸거나 새로 그린다.
// 상자 안을 끌면 옮기고, 가장자리나 모서리를 끌면 크기가 바뀌고, 상자 밖에서 끌면 새로 그린다. 놓는 순간 저장한다
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useWork } from "@/entities/project/index.js";
import { saveRoi } from "../api/roi.js";

const EDGE = 8;
const CURSORS = {
  n: "ns-resize",
  s: "ns-resize",
  e: "ew-resize",
  w: "ew-resize",
  ne: "nesw-resize",
  sw: "nesw-resize",
  nw: "nwse-resize",
  se: "nwse-resize",
  move: "move",
};

export default {
  setup() {
    const W = useWork(),
      d = computed(() => W.d);
    const caps = W.d.captions,
      startT =
        W.cur || (caps[0] ? caps[Math.floor(caps.length / 2)].start : 300);
    const src = ref(W.P("/frame?t=" + startT));
    const img = ref(null),
      wrap = ref(null),
      k = ref(0),
      live = ref(null),
      cursor = ref("crosshair"),
      autoBusy = ref(false);
    const roi = computed(() => {
      const i = d.value.info,
        y = Math.round(i.height * 0.7);
      return d.value.roi || { x: 0, y, w: i.width, h: i.height - y };
    });
    const form = reactive({ x: 0, y: 0, w: 0, h: 0 });
    watch(roi, (r) => Object.assign(form, { x: r.x, y: r.y, w: r.w, h: r.h }), {
      immediate: true,
    });
    const box = computed(() => {
      const r = live.value || roi.value,
        s = k.value;
      return {
        left: r.x * s + "px",
        top: r.y * s + "px",
        width: r.w * s + "px",
        height: r.h * s + "px",
      };
    });
    const measure = () => {
      if (img.value && img.value.clientWidth)
        k.value = img.value.clientWidth / d.value.info.width;
    };
    async function save(r) {
      try {
        W.d.roi = await saveRoi(W.pid, r);
      } catch (e) {
        alert(e.message);
      }
    }
    async function auto() {
      autoBusy.value = true;
      try {
        W.d.roi = await saveRoi(W.pid, { auto: true });
      } catch (e) {
        alert(e.message);
      }
      autoBusy.value = false;
    }
    const refresh = () => {
      src.value = W.P("/frame?t=" + W.videoTime() + "&_=" + Date.now());
    };

    /* ----- 상자 끌기 ----- */
    let drag = null;
    const pos = (e) => {
      const b = wrap.value.getBoundingClientRect(),
        s = k.value;
      return { x: (e.clientX - b.left) / s, y: (e.clientY - b.top) / s, k: s };
    };
    const zone = (p, r) => {
      const ex = EDGE / p.k;
      if (!(
        p.x >= r.x - ex &&
        p.x <= r.x + r.w + ex &&
        p.y >= r.y - ex &&
        p.y <= r.y + r.h + ex
      ))
        return null;
      const l = Math.abs(p.x - r.x) <= ex,
        rt = Math.abs(p.x - (r.x + r.w)) <= ex,
        t = Math.abs(p.y - r.y) <= ex,
        b = Math.abs(p.y - (r.y + r.h)) <= ex;
      return (t ? "n" : b ? "s" : "") + (l ? "w" : rt ? "e" : "") || "move";
    };
    function hover(e) {
      if (drag || !k.value) return;
      const z = zone(pos(e), roi.value);
      cursor.value = z ? CURSORS[z] : "crosshair";
    }
    function down(e) {
      if (!k.value) return;
      const p = pos(e),
        r = { ...roi.value },
        z = zone(p, r);
      drag = { z: z || "new", p0: p, r0: r };
      live.value = z ? r : { x: p.x, y: p.y, w: 0, h: 0 };
    }
    function move(e) {
      if (!drag) return;
      const p = pos(e),
        dx = p.x - drag.p0.x,
        dy = p.y - drag.p0.y,
        r0 = drag.r0,
        W_ = d.value.info.width,
        H = d.value.info.height;
      let r;
      if (drag.z === "new")
        r = {
          x: Math.min(drag.p0.x, p.x),
          y: Math.min(drag.p0.y, p.y),
          w: Math.abs(dx),
          h: Math.abs(dy),
        };
      else if (drag.z === "move")
        r = { x: r0.x + dx, y: r0.y + dy, w: r0.w, h: r0.h };
      else {
        let x1 = r0.x,
          y1 = r0.y,
          x2 = r0.x + r0.w,
          y2 = r0.y + r0.h;
        if (drag.z.includes("w")) x1 += dx;
        if (drag.z.includes("e")) x2 += dx;
        if (drag.z.includes("n")) y1 += dy;
        if (drag.z.includes("s")) y2 += dy;
        r = {
          x: Math.min(x1, x2),
          y: Math.min(y1, y2),
          w: Math.abs(x2 - x1),
          h: Math.abs(y2 - y1),
        };
      }
      r.x = Math.max(0, Math.min(r.x, W_ - 4));
      r.y = Math.max(0, Math.min(r.y, H - 4));
      r.w = Math.max(4, Math.min(r.w, W_ - r.x));
      r.h = Math.max(4, Math.min(r.h, H - r.y));
      live.value = r;
    }
    async function up() {
      if (!drag) return;
      const r = live.value;
      drag = null;
      if (r.w >= 8 && r.h >= 8)
        await save({
          x: Math.round(r.x),
          y: Math.round(r.y),
          w: Math.round(r.w),
          h: Math.round(r.h),
        });
      live.value = null; // 저장한 상자가 올 때까지 끈 자리에 둔다
    }
    onMounted(() => {
      addEventListener("mousemove", move);
      addEventListener("mouseup", up);
      addEventListener("resize", measure);
    });
    onUnmounted(() => {
      removeEventListener("mousemove", move);
      removeEventListener("mouseup", up);
      removeEventListener("resize", measure);
    });
    return {
      src,
      img,
      wrap,
      cursor,
      autoBusy,
      form,
      box,
      measure,
      save,
      auto,
      refresh,
      hover,
      down,
    };
  },
  template: `<div class="card"><strong>자막 영역</strong> <span class="muted">읽기 전에 빨간 상자가 자막을 모두 덮고 성경 구절 상자는 피하는지 확인하세요.</span>
      <div ref="wrap" class="roiwrap" :style="{cursor}" @mousemove="hover" @mousedown.prevent="down">
        <img ref="img" class="roiimg" :src="src" alt="자막 영역 미리보기" draggable="false" @load="measure">
        <div class="roibox" :style="box"><i class="nw"></i><i class="ne"></i><i class="sw"></i><i class="se"></i><i class="n"></i><i class="s"></i><i class="w"></i><i class="e"></i></div>
      </div>
      <div class="muted" style="margin-bottom:6px">상자 안을 끌면 옮기고, 가장자리나 모서리를 끌면 크기가 바뀝니다. 상자 밖에서 끌면 새로 그립니다. 놓는 순간 저장됩니다.</div>
      <div class="row">
        <label>x <input v-model.number="form.x" type="number" style="width:70px"></label>
        <label>y <input v-model.number="form.y" type="number" style="width:70px"></label>
        <label>너비 <input v-model.number="form.w" type="number" style="width:70px"></label>
        <label>높이 <input v-model.number="form.h" type="number" style="width:70px"></label>
        <button class="small" @click="save({...form})">적용</button><button class="small" :disabled="autoBusy" @click="auto">자동 감지</button>
        <button class="small" @click="refresh">현재 장면으로 미리보기</button>
      </div>
    </div>`,
};
