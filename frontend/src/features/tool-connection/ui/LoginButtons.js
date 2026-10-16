// 로그인(로그인 안 됨), 다른 계정으로 로그인(지금 로그인이 잠시 풀린다고 묻는다), 로그아웃(설정 해제, 묻는다).
// 로그인은 Codex만, 로그아웃은 Codex와 Antigravity만 화면에서 한다. 단추 줄에 그대로 늘어놓도록 감싸는 요소 없이 그린다
import { runToolAction } from "../model/run.js";

export default {
  props: ["x"],
  emits: ["reload"],
  setup(props, { emit }) {
    function login() {
      if (
        props.x.logged_in &&
        !confirm(
          "새로 로그인을 시작하면 지금 로그인이 잠시 풀립니다. 새 로그인을 끝내지 않으면(취소, 15분 지남) 지금 로그인을 되살립니다. 시작할까요?",
        )
      )
        return;
      runToolAction(emit, props.x.tool, "login");
    }
    function logout() {
      if (
        confirm(
          "로그아웃하면 다시 로그인할 때까지 이 도구를 쓸 수 없습니다. 로그아웃할까요?",
        )
      )
        runToolAction(emit, props.x.tool, "logout", true);
    }
    return { login, logout };
  },
  template: `<button v-if="x.can_login&&!x.logged_in" class="small primary" @click="login">로그인</button>
        <button v-if="x.can_login&&x.logged_in" class="small" @click="login">다른 계정으로 로그인</button>
        <button v-if="x.can_logout&&x.logged_in!==false" class="small" @click="logout">로그아웃 (설정 해제)</button>`,
};
