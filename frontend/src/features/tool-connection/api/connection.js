import { api } from "@/shared/api/index.js";

// 도구 하나(tool)의 연결 동작: test(연결 시험, 몇 분 걸릴 수 있다), login(Codex 기기 로그인 시작), cancel(로그인 취소), logout
export const toolAction = (tool, action) =>
  api(`/api/tools/${tool}/${action}`, "POST", {});
