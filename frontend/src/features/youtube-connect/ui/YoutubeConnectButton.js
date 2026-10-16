// 유튜브 연결(다시 연결): 새 창을 먼저 열고(팝업 막기를 피하려고), 서버가 준 구글 로그인 주소로 보낸다.
// 로그인이 끝나 돌아오는 주소가 127.0.0.1이라 서버 PC의 브라우저에서 해야 한다. 단추 글은 slot으로 받는다
import { startYoutubeLogin } from "../api/login.js";

export default {
  setup() {
    async function connect() {
      const w = window.open("", "_blank");
      try {
        const { url } = await startYoutubeLogin();
        w.location = url;
      } catch (e) {
        w.close();
        alert(e.message);
      }
    }
    return { connect };
  },
  template: `<button class="small" @click="connect"><slot/></button>`,
};
