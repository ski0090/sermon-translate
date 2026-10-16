// 쇼츠 화면 왼쪽 목록에서 영상 하나의 배지: 후보 고르는 중·만드는 중, 후보 고르기 실패, n/m개 완성(다시 만들 수), 아직 없음
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
              (x.stale ? " · 다시 만들 것 " + x.stale : ""),
          }
        : { cls: "", text: "아직 없음" };

// 같은 목록에서 유튜브에 올린 쇼츠 수 배지(n/m 올림, 다 올렸으면 초록). 이미 올린 게 있거나, 유튜브가 연결되어 있고
// 만든 쇼츠가 있을 때만 보이고(그 밖에는 null) 0개도 보인다
export const shortsUploadBadge = (x, connected) =>
  x.count && (x.uploaded || (connected && x.done + (x.stale || 0)))
    ? {
        cls: x.uploaded >= x.count ? "ok" : "",
        text: "유튜브 " + x.uploaded + "/" + x.count + " 올림",
      }
    : null;
