import { api } from "@/shared/api/index.js";

// 자동 진행 상태: 켜짐, 목소리, 영상 수, 지금 하는 영상, 대기열, 실패와 건너뛴 영상
export const fetchBatch = () => api("/api/batch");
