// 도구 하나(x)의 모델 목록. 서버가 쓸 수 있는 모델부터 정렬해 주고, 모델마다 {ok, why, note, limits}를 준다

const info = (x, v) => (x.model_info || {})[v] || {};

// 모델 고르기 칸: 쓸 수 없는 모델은 고르지 못하게 하고(지금 고른 모델은 빼고), 목록에 없는 모델을 직접 골라 두었으면 그것도 보인다
export function modelOptions(x) {
  const ms = x.models || [],
    m = x.model;
  return ms
    .map(([v, l]) => {
      const i = info(x, v);
      return {
        v,
        t:
          l +
          (v && v !== l ? " (" + v + ")" : "") +
          (i.ok === false ? " — 사용 불가" : ""),
        off: i.ok === false && v !== m,
      };
    })
    .concat(
      m && !ms.some(([v]) => v === m) ? [{ v: m, t: m, off: false }] : [],
    );
}
// 모델별 사용 가능 여부 표의 줄
export const modelRows = (x) =>
  (x.models || []).map(([v, l]) => ({
    v,
    l,
    ok: info(x, v).ok,
    why: info(x, v).why || info(x, v).note,
    limits: info(x, v).limits || [],
  }));
// 쓴 한도(0~1)의 글과 색(70% 넘으면 주황, 90% 넘으면 빨강)
export const limitPct = (u) => Math.round(u * 100) + "%";
export const limitColor = (u) =>
  u >= 0.9 ? "var(--bad)" : u >= 0.7 ? "var(--warn)" : "var(--text)";
