import { api } from "@/shared/api/index.js";

// 도구 하나의 설정 바꾸기: {tool, enabled} 또는 {tool, model}(빈 모델이면 도구의 기본 모델)
export const saveTool = (body) => api("/api/tools", "POST", body);
