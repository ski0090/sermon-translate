import { api } from "@/shared/api/index.js";

// 구글 드라이브 연결 여부와 지금 내려받는 영상({available, job})
export const fetchDriveStatus = () => api("/api/drive/status");
// 폴더 하나의 하위 폴더와 영상 파일. shared면 공유 문서함
export const listDrive = (path, shared) =>
  api(
    `/api/drive/list?path=${encodeURIComponent(path)}&shared=${shared ? "1" : ""}`,
  );
// 영상을 이 PC(projects/_drive)에 내려받아 프로젝트로 만든다. 이미 받은 영상은 다시 받지 않는다
export const importDrive = (path, size, shared) =>
  api("/api/drive/import", "POST", { path, size, shared });
export const cancelDriveImport = () => api("/api/drive/cancel", "POST", {});
