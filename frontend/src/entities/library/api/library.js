import { api } from "@/shared/api/index.js";

// refresh면 드라이브 목록을 기다리지 않고 새로 읽게 한다(새로고침 버튼)
export const fetchLibrary = (refresh) =>
  api("/api/library" + (refresh ? "?refresh=1" : ""));
