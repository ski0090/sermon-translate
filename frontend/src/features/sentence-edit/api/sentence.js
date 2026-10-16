// 문장 하나 고치기: 글·읽는 글·속도·앞 쉼·확인함(save), 지우기, 자막 그림 cap에서 나누기, 다음 문장과 합치기, 음성 다시 만들기
import { api } from "@/shared/api/index.js";
import { projectPath } from "@/entities/project/index.js";

const path = (pid, sid, rest = "") =>
  projectPath(pid, "/sentence/" + sid + rest);

export const saveSentence = (pid, sid, body) =>
  api(path(pid, sid), "POST", body);
export const deleteSentence = (pid, sid) => api(path(pid, sid), "DELETE");
export const splitSentence = (pid, sid, cap) =>
  api(path(pid, sid, "/split"), "POST", { cap });
export const mergeSentence = (pid, sid) =>
  api(path(pid, sid, "/merge"), "POST", {});
export const regenerateVoice = (pid, sid) =>
  api(path(pid, sid, "/tts"), "POST", {});
