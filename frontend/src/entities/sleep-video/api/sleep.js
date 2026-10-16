import { api } from "@/shared/api/index.js";

// 음성을 만든 영상마다의 음성 영상 상태와 자동 만들기 켜짐({items, auto, yt})
export const fetchSleepList = () => api("/api/sleep");
// 영상 하나(x.dir)의 음성 영상 API와 파일 주소(/api/p/<프로젝트>/sleep...)
export const sleepPath = (x, p) =>
  `/api/p/${encodeURIComponent(x.dir)}/sleep${p}`;
