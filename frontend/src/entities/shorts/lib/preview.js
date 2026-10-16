// 쇼츠 카드의 미리 보기 그림과 강조 구절

// 미리 보기 그림 주소에 붙이는 값: 그림에 들어가는 설정이 바뀔 때만 바뀌어 그 카드의 그림만 새로 받는다
const hash = (s) => {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  return h.toString(36);
};
export const previewVersion = (it) =>
  hash(JSON.stringify([it.title, it.start, it.end, it.emph, it.xpos]));
// 문장 하나를 강조 구절로 나눈 조각 [{text, mark, a, b}]
export function marks(text, ph) {
  const f = new Array(text.length).fill(false);
  (ph || []).forEach((p) => {
    const i = text.indexOf(p);
    if (i >= 0) for (let k = i; k < i + p.length; k++) f[k] = true;
  });
  const out = [];
  let i = 0;
  while (i < text.length) {
    let j = i;
    while (j < text.length && f[j] === f[i]) j++;
    out.push({ text: text.slice(i, j), mark: f[i], a: i, b: j });
    i = j;
  }
  return out;
}
