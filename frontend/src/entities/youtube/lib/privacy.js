// 유튜브 공개 범위 이름(모르는 값은 비공개로 본다: 이 앱은 비공개로 올린다)
export const privacyName = (p) =>
  ({ public: "공개", unlisted: "일부 공개", private: "비공개" })[p] || "비공개";
