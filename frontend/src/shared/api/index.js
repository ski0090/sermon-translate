// API 부르기: 화면 서버(frontend/serve.py)가 /api/...를 API 서버로 넘긴다. 실패하면 서버가 준 error 글로 오류를 낸다
export async function api(path, method = "GET", body) {
  const r = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "오류 " + r.status);
  return j;
}
