import { api } from "@/shared/api/index.js";

export const startBatch = (voice) =>
  api("/api/batch", "POST", { action: "start", voice });
// 지금 하던 단계까지만 하고 멈춘다
export const stopBatch = () => api("/api/batch", "POST", { action: "stop" });
