// 프로젝트 목록을 거르는 단계(왼쪽 메뉴, #/projects/<단계>)
export const STAGES = [
  ["todo", "진행 전"],
  ["review", "정리와 검수"],
  ["scan", "자막 읽기"],
  ["tts", "음성"],
  ["export", "내보내기"],
];
export const stageName = (k) => (STAGES.find((x) => x[0] === k) || [])[1];
