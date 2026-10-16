// 음성 영상을 유튜브에 비공개로 올리기와 올리기 취소
import { api } from "@/shared/api/index.js";
import { sleepPath } from "@/entities/sleep-video/index.js";

export const uploadSleep = (x) => api(sleepPath(x, "/youtube"), "POST", {});
export const cancelSleepUpload = (x) =>
  api(sleepPath(x, "/youtube/cancel"), "POST", {});
