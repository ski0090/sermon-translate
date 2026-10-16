import { api } from "@/shared/api/index.js";

// 도구(claude, codex, agy)에 아주 짧게 물어 지금 사용량을 읽게 한다(Codex는 한 번 불러 보고, agy는 /usage)
export const checkUsage = (tool) =>
  api("/api/usage/all/check", "POST", { tool });
