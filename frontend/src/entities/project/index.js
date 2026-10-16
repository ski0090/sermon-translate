// 프로젝트(영상 하나의 더빙 작업): 단계, 진행 글, 돌고 있는 작업, 프로젝트 API, 작업 화면의 상태(W) 꺼내기
export { STAGES, stageName } from "./config/stages.js";
export { STEPS, STEP_ORDER } from "./config/steps.js";
export { projStage, progressText } from "./lib/stage.js";
export { jobName, jobMsg } from "./lib/job.js";
export { default as JobBar } from "./ui/JobBar.js";
export {
  projectPath,
  fetchProject,
  fetchPlan,
  fetchJob,
  requestJob,
  cancelJob,
  saveProjectSettings,
} from "./api/project.js";
export { provideWork, useWork } from "./model/work.js";
