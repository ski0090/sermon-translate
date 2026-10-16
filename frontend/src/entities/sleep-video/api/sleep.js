import { api } from "@/shared/api/index.js";

// 음성을 만든 영상마다의 음성 영상 상태와 자동 만들기 켜짐({items, auto, yt})
export const fetchSleepList = () => api("/api/sleep");
