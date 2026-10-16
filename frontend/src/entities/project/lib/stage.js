// 프로젝트 요약(목록의 한 줄)에서 머문 단계와 진행 글을 계산한다

// 프로젝트가 머문 단계: 돌고 있는 작업 > 만든 결과. 서버는 review 단계를 따로 적지 않아 문장이 있으면 정리와 검수로 본다
export function projStage(p) {
  const j = p.job;
  if (j)
    return j.queued
      ? "tts"
      : { tidy: "review", tts: "tts", export: "export" }[j.kind] || "scan";
  if (p.exported || p.step === "export") return "export";
  if (p.tts || p.step === "tts") return "tts";
  if (p.sentences) return "review";
  return p.captions || p.step === "scan" ? "scan" : "todo";
}
export function progressText(p) {
  const parts = [];
  if (p.captions) parts.push(`자막 ${p.read}/${p.captions}장`);
  if (p.sentences) parts.push(`문장 ${p.sentences}개`);
  if (p.sentences) parts.push(`음성 ${p.tts}/${p.sentences}`);
  if (p.cuts) parts.push(`잘라내기 ${p.cuts}개`);
  if (p.exported) parts.push("내보내기 완료");
  return parts.join(" · ") || "아직 자막을 읽지 않음";
}
