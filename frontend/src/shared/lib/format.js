// 글 형식: 재생 시각(분:초), 날짜·시각, 지난 시간, 파일 크기
export const fmt = (t) => {
  t = Math.max(0, t || 0);
  const m = Math.floor(t / 60),
    s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
};
export const when = (t) =>
  new Date(t * 1000).toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
export const ago = (t) => {
  const m = Math.round((Date.now() / 1000 - t) / 60);
  return m < 1 ? "방금" : m < 60 ? m + "분 전" : Math.round(m / 60) + "시간 전";
};
export const fsize = (b) =>
  b < 0
    ? ""
    : b >= 2 ** 30
      ? (b / 2 ** 30).toFixed(1) + "GB"
      : Math.max(1, Math.round(b / 2 ** 20)) + "MB";
