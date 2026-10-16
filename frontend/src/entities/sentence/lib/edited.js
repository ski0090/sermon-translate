// AI가 고친 문장 알아보기와, 읽은 글에서 고친 글자 표시

// AI 정리가 읽은 글(raw)을 바꿨는지. 띄어쓰기와 문장 부호만 다르면 바뀐 것으로 보지 않는다
export const edited = (s) => {
  const n = (t) => (t || "").replace(/[\s.,?!…"'“”‘’]/g, "");
  return !!s.ai && n(s.ai) !== n(s.raw);
};
// 글자 단위 LCS로 b에서 a와 다른 글자를 표시한 조각 [{t, m}]. 같은 쌍은 다시 계산하지 않는다
const diffCache = new Map();
export function diffParts(a, b) {
  const key = a + "\u0000" + b;
  if (diffCache.has(key)) return diffCache.get(key);
  const n = a.length,
    m = b.length;
  let out;
  if (n * m > 40000) out = [{ t: b, m: false }];
  else {
    const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--)
      for (let j = m - 1; j >= 0; j--)
        dp[i][j] =
          a[i] === b[j]
            ? dp[i + 1][j + 1] + 1
            : Math.max(dp[i + 1][j], dp[i][j + 1]);
    out = [];
    const push = (c, mk) => {
      const l = out[out.length - 1];
      if (l && l.m === mk) l.t += c;
      else out.push({ t: c, m: mk });
    };
    let i = 0,
      j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        push(b[j], false);
        i++;
        j++;
      } else if (dp[i + 1][j] >= dp[i][j + 1]) i++;
      else {
        push(b[j], true);
        j++;
      }
    }
    while (j < m) push(b[j++], true);
  }
  diffCache.set(key, out);
  return out;
}
