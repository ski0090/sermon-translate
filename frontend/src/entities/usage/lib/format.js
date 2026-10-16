// 사용량 글 형식: 읽은 때(며칠 전까지), 한도 기간(분 → 분·시간·일), 토큰 수(K, M)
export const since = (t) => {
  if (!t) return "아직 모름";
  const m = Math.round((Date.now() / 1000 - t) / 60);
  return m < 1
    ? "방금"
    : m < 60
      ? m + "분 전"
      : m < 1440
        ? Math.round(m / 60) + "시간 전"
        : Math.round(m / 1440) + "일 전";
};
export const span = (m) =>
  !m
    ? ""
    : m >= 1440
      ? Math.round(m / 1440) + "일"
      : m >= 60
        ? Math.round(m / 60) + "시간"
        : m + "분";
export const tok = (n) =>
  !n
    ? "0"
    : n >= 1e6
      ? (n / 1e6).toFixed(1) + "M"
      : n >= 1e3
        ? Math.round(n / 1e3) + "K"
        : String(n);
