// 쇼츠 하나 고치기. 모두 그 영상의 쇼츠 상태 전체를 돌려준다
import { api } from "@/shared/api/index.js";
import { shortsPath } from "@/entities/shorts/index.js";

// body만 있으면 제목·구간·강조·가로 위치를 고치고, path로 만들기(/render)·유튜브 올리기(/youtube)·올리기 취소(/youtube/cancel)
export const postShort = (pid, id, body, path = "") =>
  api(shortsPath(pid, "/" + id + path), "POST", body);
// 이 PC의 영상 파일도 지운다(구글 드라이브와 유튜브에 올린 것은 그대로)
export const deleteShort = (pid, id) =>
  api(shortsPath(pid, "/" + id), "DELETE");
