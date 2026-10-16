// 타임라인 아래 잘라내기 단추: 고른 구간(W.sel) 잘라내기, 자막 없음·찬양 후보 모두 잘라내기, 잘라내기 구간 목록(✕로 빼기).
// 타임라인 줄(.tlbar)에 그대로 늘어놓도록 감싸는 요소 없이 그린다
import { fmt } from "@/shared/lib/index.js";
import { useWork } from "@/entities/project/index.js";
import { saveCuts } from "../api/cuts.js";

export default {
  setup() {
    const W = useWork();
    async function setCuts(cuts) {
      try {
        await saveCuts(W.pid, cuts);
      } catch (e) {
        alert(e.message);
      }
      await W.reload();
    }
    function cutSel() {
      if (!W.sel) return;
      const cuts = W.d.cuts.concat([
        { start: W.sel[0], end: W.sel[1], label: "잘라내기" },
      ]);
      W.sel = null;
      setCuts(cuts);
    }
    function cutCands() {
      const d = W.d,
        cands = d.ranges.gaps
          .map((g) => ({ ...g, label: "자막 없음" }))
          .concat(d.ranges.lyrics.map((g) => ({ ...g, label: "찬양" })));
      if (!cands.length) return alert("잘라낼 후보 구간이 없습니다.");
      if (
        !confirm(
          `자막 없음 ${d.ranges.gaps.length}개, 찬양 후보 ${d.ranges.lyrics.length}개 구간을 잘라내기로 지정할까요?`,
        )
      )
        return;
      setCuts(d.cuts.concat(cands));
    }
    function uncut(i) {
      const cuts = W.d.cuts.slice();
      cuts.splice(i, 1);
      setCuts(cuts);
    }
    return { W, cutSel, cutCands, uncut, fmt };
  },
  template: `<button class="small" :disabled="!W.sel" @click="cutSel">선택 구간 잘라내기</button>
        <button class="small" @click="cutCands">자막 없음 · 찬양 후보 모두 잘라내기</button>
        <span><span v-for="(c,i) in W.d.cuts" :key="i+':'+c.start" class="badge" style="margin-left:6px">{{c.label||"잘라내기"}} {{fmt(c.start)}}–{{fmt(c.end)}} <a style="cursor:pointer;color:var(--bad)" @click="uncut(i)">✕</a></span></span>`,
};
