import { api } from "@/shared/api/index.js";
import { projectPath } from "@/entities/project/index.js";

// 자막 영역(빨간 상자 {x, y, w, h})을 저장하거나({auto: true}면) 자동으로 찾는다. 저장된 영역을 돌려준다
export const saveRoi = (pid, body) =>
  api(projectPath(pid, "/roi"), "POST", body);
