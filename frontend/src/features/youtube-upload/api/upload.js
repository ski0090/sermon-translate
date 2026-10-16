import { api } from "@/shared/api/index.js";

// 드라이브 영상 하나(path)의 더빙 영상을 유튜브에 올리기(이어서 올리기·재생목록과 자막 넣기 포함)와 올리기 취소
export const uploadToYoutube = (path) =>
  api("/api/youtube/upload", "POST", { path });
export const cancelYoutubeUpload = (path) =>
  api("/api/youtube/cancel", "POST", { path });
