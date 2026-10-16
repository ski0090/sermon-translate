// 영상의 쇼츠 상태: 진행 전(아직 없음) · 만드는 중(고르거나 만드는 중, 아직 안 만든 쇼츠가 있음) · 완성
export const shStage = (x) =>
  x.busy || x.done < x.count ? "making" : x.count ? "done" : "todo";
