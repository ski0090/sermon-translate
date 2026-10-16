// 프로젝트에서 지금 돌고 있는 작업(자막 읽기, 문장 정리, 음성, 내보내기)의 이름과 알림 글

// 지금 돌고 있는 작업 이름(프로젝트 단계가 아니라)
export const jobName = (j) =>
  j.queued
    ? "음성 대기"
    : {
        scan: "자막 읽기",
        read: "자막 읽기",
        tidy: "문장 정리",
        tts: "음성",
        export: "내보내기",
      }[j.kind] || "작업";
export const jobMsg = (j) =>
  (j.msg || "작업 중") + (j.resumed ? " · 재시작 후 다시 하는 중" : "");
