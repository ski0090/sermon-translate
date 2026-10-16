// 영상의 음성 영상 상태: 아직 없음 · 만드는 중(대기 포함) · 완성
export const svStage = (x) =>
  x.status === "queued" || x.status === "rendering"
    ? "making"
    : x.has_file
      ? "done"
      : "todo";
