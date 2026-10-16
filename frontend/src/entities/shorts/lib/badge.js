// 쇼츠 화면 왼쪽 목록에서 영상 하나의 배지: 후보 고르는 중·만드는 중, 후보 고르기 실패, n/m개 완성(다시 만들 수, 유튜브에 올린 수), 아직 없음
export const shortsBadge = (x) =>
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
            cls: x.stale ? "warn" : "",
            text:
              x.done +
              "/" +
              x.count +
              "개 완성" +
              (x.stale ? " · 다시 만들 것 " + x.stale : "") +
              (x.uploaded ? " · 유튜브 " + x.uploaded : ""),
          }
        : { cls: "", text: "아직 없음" };
