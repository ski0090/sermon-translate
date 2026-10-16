import { api } from "@/shared/api/index.js";

// AI 도구별 사용량(Claude 한도, Codex 한도, Antigravity /usage)과 날짜별 호출 수·토큰, 오늘 자동 작업 도구
export const fetchUsage = () => api("/api/usage/all");
