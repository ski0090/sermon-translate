// 자동 진행 한 줄 요약(영상 수가 없으면 빈 글)
export function batchSummary(b) {
  const n = (k) => (b.count || {})[k] || 0;
  return b.total
    ? `완료 ${n("done")} / ${b.total}편 · 검수 대기 ${n("ready")} · 자막 대기 ${n("waiting")} · 음성 대기열 ${b.voice_waiting || 0}편 · 실패 ${n("error")}${n("skipped") ? ` · 같은 영상이라 건너뜀 ${n("skipped")}` : ""}`
    : "";
}
