// 드라이브 영상 하나(프로젝트 목록의 한 줄)의 상태
import { fsize } from "@/shared/lib/index.js";
import {
  jobName,
  progressText,
  projStage,
  stageName,
} from "@/entities/project/@x/library.js";

// 드라이브 영상 하나의 상태: 진행 중 > 내려받는 중 > 이 PC의 프로젝트 > 드라이브의 결과 > 이전 작업 > 시작 전
// group은 완료·진행 중·시작 전 묶음, job이 있으면 진행 막대로, 없으면 text를 보인다
export function libState(it) {
  const p = it.project;
  if (p && p.job)
    return {
      group: "run",
      label: "진행 중 · " + jobName(p.job),
      cls: "ok",
      job: p.job,
      stage: projStage(p),
    };
  if (it.importing)
    return {
      group: "run",
      label: "내려받는 중",
      cls: "ok",
      job: it.importing,
      stage: "todo",
    };
  if (p && p.exported)
    return {
      group: "done",
      label: "완료",
      cls: "ok",
      text: progressText(p),
      stage: "export",
    };
  if (p) {
    const k = projStage(p);
    return {
      group: "run",
      label: stageName(k),
      cls: "warn",
      text: progressText(p),
      stage: k,
    };
  }
  if (it.drive_done)
    return {
      group: "done",
      label: "완료",
      cls: "ok",
      text: "구글 드라이브에 결과 있음",
      stage: "export",
    };
  if (it.legacy)
    return {
      group: "run",
      label: "이전 작업 있음",
      cls: "warn",
      text: "다른 PC에서 작업한 기록이 드라이브에 있음",
      stage: "todo",
    };
  return {
    group: "todo",
    label: "시작 전",
    cls: "",
    text: fsize(it.size),
    stage: "todo",
  };
}
