// 쇼츠 만들기: Claude로 후보 3개 고르기, 시각을 정해 직접 추가(영상의 쇼츠 상태 전체를 돌려준다), 내보내기 뒤 자동 후보 켜고 끄기
import { api } from "@/shared/api/index.js";
import { shortsPath } from "@/entities/shorts/index.js";

export const suggestShorts = (pid) =>
  api(shortsPath(pid, "/suggest"), "POST", {});
export const addShort = (pid, at) =>
  api(shortsPath(pid, "/new"), "POST", { at });
export const setAutoSuggest = (auto) => api("/api/shorts", "POST", { auto });
