import { api } from "@/shared/api/index.js";
import { projectPath } from "@/entities/project/index.js";

// 잘라내기 구간 전체를 바꾼다([{start, end, label}])
export const saveCuts = (pid, cuts) =>
  api(projectPath(pid, "/cuts"), "POST", { cuts });
