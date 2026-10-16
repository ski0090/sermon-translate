import { api } from "@/shared/api/index.js";

// 구글 로그인 주소를 받는다({url}). 서버는 로그인이 끝나 돌아올 127.0.0.1 주소를 잠시 연다
export const startYoutubeLogin = () => api("/api/youtube/login", "POST", {});
