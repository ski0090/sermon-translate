// 문장 목록 거르기(W.filter): 전체(all), 확인 필요(check), 자동 수정됨(ai), 길이 초과(over: 음성 계획 p에서 넘침)
import { edited } from "./edited.js";

export const isOver = (p) => p.overflow || p.fixed_overflow;
export function inFilter(s, filter, p) {
  if (filter === "check") return s.check;
  if (filter === "ai") return edited(s);
  if (filter === "over") return p && isOver(p);
  return true;
}
