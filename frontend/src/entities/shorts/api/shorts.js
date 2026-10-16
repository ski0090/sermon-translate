import { api } from "@/shared/api/index.js";

// 쇼츠를 만들 수 있는 영상 목록과 자동 후보 켜짐({items, auto})
export const fetchShortsList = () => api("/api/shorts");
