import { api } from "@/shared/api/index.js";

// 도구마다 설치·로그인·플랜·모델·모델별 사용 가능 여부와 오늘 자동 작업 도구({tools, today}).
// fresh면 서버가 기억해 둔 값을 쓰지 않고 다시 확인한다
export const fetchTools = (fresh) =>
  api("/api/tools" + (fresh ? "?fresh=1" : ""));
