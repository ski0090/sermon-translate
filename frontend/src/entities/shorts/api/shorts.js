import { api } from "@/shared/api/index.js";

// 쇼츠를 만들 수 있는 영상 목록과 자동 후보 켜짐({items, auto})
export const fetchShortsList = () => api("/api/shorts");
// 영상 하나의 쇼츠 API와 파일 주소(/api/p/<프로젝트>/shorts/...)
export const shortsPath = (pid, path) =>
  `/api/p/${encodeURIComponent(pid)}/shorts${path || ""}`;
// 영상 하나의 쇼츠 목록과 후보 고르기 상태. lite면 문장 목록은 빼고 받는다
export const fetchShorts = (pid, lite) =>
  api(shortsPath(pid, lite ? "?lite=1" : ""));
