// 프로젝트 하나의 API. 영상·그림·음성 같은 파일 주소도 projectPath로 만든다(/api/p/<프로젝트>/...)
import { api } from "@/shared/api/index.js";

export const projectPath = (pid, path = "") =>
  `/api/p/${encodeURIComponent(pid)}${path}`;

// 프로젝트 전체(자막, 문장, 잘라내기, 설정, 돌고 있는 작업)
export const fetchProject = (pid) => api(projectPath(pid));
// 문장마다 음성을 어디에 얼마나 빠르게 넣는지(길이 초과 표시에 쓴다)
export const fetchPlan = (pid) => api(projectPath(pid, "/plan"));
export const fetchJob = (pid) => api(projectPath(pid, "/job"));
// 작업 시작(kind: scan, tidy, tts, export)과 중단
export const requestJob = (pid, kind, params = {}) =>
  api(projectPath(pid, "/job"), "POST", { kind, ...params });
export const cancelJob = (pid) =>
  api(projectPath(pid, "/job/cancel"), "POST", {});
export const saveProjectSettings = (pid, body) =>
  api(projectPath(pid, "/settings"), "POST", body);
