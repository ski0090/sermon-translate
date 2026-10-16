// 주소의 # 뒤를 읽어 지금 화면(nav.route)을 정한다(#/projects/<단계>, #/shorts/<상태>/<프로젝트>, #/sleep/<상태>,
// #/usage, #/schedule, #/tools, #/p/<프로젝트>). 거르기는 그 목록의 단계·상태 이름일 때만 받고, 아니면 전체(all)다
import { nav } from "@/shared/router/index.js";
import { STAGES } from "@/entities/project/index.js";
import { SH_STAGES } from "@/entities/shorts/index.js";
import { SV_STAGES } from "@/entities/sleep-video/index.js";

const known = (list, f) => (list.some((x) => x[0] === f) ? f : "all");
function parseRoute() {
  const [view, filter, pid] = location.hash.replace(/^#\/?/, "").split("/");
  if (view === "p")
    return {
      view: "work",
      filter: "all",
      pid: decodeURIComponent(filter || ""),
    };
  if (["schedule", "usage", "tools"].includes(view))
    return { view, filter: "all" };
  if (view === "shorts")
    return {
      view,
      filter: known(SH_STAGES, filter),
      pid: pid ? decodeURIComponent(pid) : null,
    };
  if (view === "sleep") return { view, filter: known(SV_STAGES, filter) };
  return { view: "projects", filter: known(STAGES, filter) };
}
// 쇼츠에서 고른 영상과 프로젝트 목록의 거르기는 다른 화면에 다녀와도 기억한다
const route = () => {
  const r = (nav.route = parseRoute());
  if (r.view === "shorts" && r.pid) nav.shPid = r.pid;
  if (r.view === "projects") nav.listFilter = r.filter;
};

export function startRouter() {
  route();
  addEventListener("hashchange", route);
}
