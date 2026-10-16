import { api } from "@/shared/api/index.js";

// 스케줄: 날마다 정한 도구·한도(days), 기본값, Fable 이어 하기, 오늘 도구와 한도, 지금 사용량, 자동 작업 쉼
export const fetchSchedule = () => api("/api/schedule");
