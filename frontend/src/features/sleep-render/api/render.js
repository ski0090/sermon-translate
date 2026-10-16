// 음성 영상 만들기: 한 편 만들기(대기열에 넣기)·멈추기, 아직 없는 영상 모두 만들기, 내보내기 뒤 자동으로 만들기 켜고 끄기
import { api } from "@/shared/api/index.js";
import { sleepPath } from "@/entities/sleep-video/index.js";

export const renderSleep = (x) => api(sleepPath(x, ""), "POST", {});
export const cancelSleep = (x) => api(sleepPath(x, "/cancel"), "POST", {});
export const renderAllSleep = () =>
  api("/api/sleep", "POST", { action: "all" });
export const setSleepAuto = (auto) => api("/api/sleep", "POST", { auto });
