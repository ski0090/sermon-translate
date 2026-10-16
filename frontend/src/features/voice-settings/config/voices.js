// 프로젝트의 목소리(F는 여성, M은 남성)와 들어 보기 소리 주소(서버가 그 목소리로 짧게 만든다)
export const VOICES = [
  "F1",
  "F2",
  "F3",
  "F4",
  "F5",
  "M1",
  "M2",
  "M3",
  "M4",
  "M5",
];
export const voiceSampleUrl = (v) => "/api/voice-sample/" + v;
