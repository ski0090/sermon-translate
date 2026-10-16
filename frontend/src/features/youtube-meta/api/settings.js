import { api } from "@/shared/api/index.js";

// 유튜브에 올릴 때 쓰는 설명·해시태그와 쇼츠·음성 영상의 제목·설명
export const fetchYoutubeSettings = () => api("/api/youtube/settings");
export const saveYoutubeSettings = (body) =>
  api("/api/youtube/settings", "POST", body);
