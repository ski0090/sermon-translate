// 주소의 # 뒤가 화면이다(#/projects/<단계>, #/shorts/<상태>/<프로젝트>, #/sleep/<상태>, #/usage, #/schedule, #/tools, #/p/<프로젝트>).
// 주소를 읽어 route를 채우는 것은 app/router이고, 여기에는 화면들이 함께 읽는 상태와 화면 옮기기만 둔다
import { reactive } from "vue";

// route는 지금 화면(view, filter, pid)이고 주소가 바뀔 때마다 새 객체로 바뀐다.
// listFilter는 마지막으로 본 프로젝트 목록의 거르기(프로젝트를 열어도 메뉴에 표시), shPid는 쇼츠에서 고른 영상,
// workName은 연 프로젝트 이름(머리줄 제목)
export const nav = reactive({
  route: { view: "projects", filter: "all" },
  listFilter: "all",
  shPid: null,
  workName: null,
});

export const openProject = (dir) => {
  location.hash = "#/p/" + encodeURIComponent(dir);
};
