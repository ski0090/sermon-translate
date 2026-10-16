// 새 프로젝트 카드: 구글 드라이브에서 영상 고르기(창은 화면이 연다: open 'drive')와 유튜브 연결 줄(설명·해시태그 창: open 'ytmeta')
import { youtubeStatus } from "@/entities/youtube/index.js";
import { YoutubeConnectButton } from "@/features/youtube-connect/index.js";

export default {
  components: { YoutubeConnectButton },
  props: ["drive"],
  emits: ["open"],
  setup() {
    // 다른 PC에서 연 화면이면 유튜브 연결은 서버 PC에서 하라고 알린다
    const remote = !["127.0.0.1", "localhost"].includes(location.hostname);
    return { yt: youtubeStatus, remote };
  },
  template: `<div class="card">
      <div class="row" style="justify-content:space-between">
        <div><strong>새 프로젝트</strong><div class="muted">{{drive&&!drive.available?"구글 드라이브가 연결되어 있지 않습니다. 서버 PC에서 rclone으로 gdrive를 연결한 뒤 다시 실행하세요(README의 구글 드라이브 연결).":"화면 아래쪽에 한국어 자막이 있는 설교 영상을 구글 드라이브에서 고르세요. 결과물은 영상과 같은 폴더 아래 \\"영상 이름 한국어 더빙\\" 폴더에 저장됩니다."}}</div></div>
        <button class="primary" :disabled="!(drive&&drive.available)" @click="$emit('open','drive')">구글 드라이브에서 선택</button>
      </div>
      <div v-if="yt" class="row" style="margin-top:10px;border-top:1px solid var(--line);padding-top:10px">
        <template v-if="yt.connected"><span class="muted">유튜브: <b>{{yt.channel||"연결됨"}}</b> 채널에 비공개로 올리고 재생목록 "{{yt.playlist}}"에 넣습니다.</span><button class="small" @click="$emit('open','ytmeta')">설명·해시태그</button><YoutubeConnectButton>다시 연결</YoutubeConnectButton></template>
        <template v-else><span class="muted">유튜브가 연결되어 있지 않습니다.{{remote?" 연결은 서버 PC의 브라우저에서 해야 합니다.":""}}{{yt.login.busy?" 로그인 창에서 계정과 채널을 고르세요.":""}}{{yt.login.error?" 오류: "+yt.login.error:""}}</span><YoutubeConnectButton>유튜브 연결</YoutubeConnectButton></template>
      </div>
    </div>`,
};
