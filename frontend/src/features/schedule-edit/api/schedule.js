// 스케줄 바꾸기({tool, default} 기본값, {fable} Fable 이어 하기, {days} 고른 날들(null이면 기본값으로)). 바뀐 스케줄을 돌려준다.
// 실패하면 알리고 null
import { api } from "@/shared/api/index.js";

export async function saveSchedule(body) {
  try {
    return await api("/api/schedule", "POST", body);
  } catch (e) {
    alert(e.message);
    return null;
  }
}
