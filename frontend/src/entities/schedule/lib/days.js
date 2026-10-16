// 스케줄의 날짜와 글: 날 열쇠(YYYY-MM-DD), 날 이름(월/일(요일)), 도구 이름, 사용량 %, 달력 칸, 주간 사용량이 초기화되는 날
import { TOOLS } from "@/entities/ai-tool/@x/schedule.js";

const pad = (n) => String(n).padStart(2, "0");
export const dayKey = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;
export const dayLabel = (k) => {
  const [y, m, d] = k.split("-").map(Number);
  return `${m}/${d}(${"일월화수목금토"[new Date(y, m - 1, d).getDay()]})`;
};
export const toolName = (t) => TOOLS[t] || "없음(모든 도구가 꺼짐)";
export const usagePct = (x) => (x == null ? "모름" : Math.round(x * 100) + "%");

// 주간 사용량이 초기화되는 날(다음 초기화 시각부터 7일마다)과 그 시각
export function resetDays(v) {
  const r = v && v.usage.seven_day.resetsAt;
  if (!r) return {};
  const out = {};
  for (let k = 0; k < 10; k++) {
    const t = new Date((r + k * 7 * 86400) * 1000);
    out[dayKey(t.getFullYear(), t.getMonth(), t.getDate())] =
      t.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
  }
  return out;
}
// y년 m월(0부터) 달력 칸: 첫 주 앞의 빈칸, 그리고 날마다 정한 값(없으면 기본값), 도구, 요일, 지난날·오늘, 초기화 시각
export function monthCells(v, y, m, resets) {
  const first = new Date(y, m, 1).getDay(),
    n = new Date(y, m + 1, 0).getDate(),
    out = [];
  for (let i = 0; i < first; i++) out.push({ k: "blank" + i, blank: true });
  for (let day = 1; day <= n; day++) {
    const k = dayKey(y, m, day),
      set = v.days[k],
      wd = (first + day - 1) % 7;
    out.push({
      k,
      day,
      set: !!set,
      lim: set || v.default,
      tool: (set && set.tool) || v.tool || "claude",
      wd,
      past: k < v.today,
      today: k === v.today,
      reset: resets[k],
    });
  }
  return out;
}
