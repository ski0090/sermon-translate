// 연결 동작을 보내고(실패하면 알리고) 도구 상태를 다시 읽게 한다. fresh면 서버가 기억해 둔 값 없이 다시 확인한다
import { toolAction } from "../api/connection.js";

export async function runToolAction(emit, tool, action, fresh) {
  try {
    await toolAction(tool, action);
  } catch (e) {
    alert(e.message);
  }
  emit("reload", fresh);
}
