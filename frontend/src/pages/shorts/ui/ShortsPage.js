// 쇼츠 화면(#/shorts/<상태>/<프로젝트>): 왼쪽은 쇼츠를 만들 수 있는 영상 목록(메뉴에서 고른 상태만), 오른쪽은 고른 영상의 쇼츠 카드.
// 카드에서 제목, 구간(문장 단위), 강조 구절, 가로 위치를 고치면 바로 저장되고, 미리 보기 그림으로 확인한 뒤
// "다시 만들기"를 누르면 영상에 반영된다. 유튜브 올리기 단추는 연결되어 있을 때만 보이므로 연결 상태를 한 번 받는다
import { onMounted } from "vue";
import { nav } from "@/shared/router/index.js";
import { youtubeStatus, fetchYoutubeStatus } from "@/entities/youtube/index.js";
import { ShortsList } from "@/widgets/shorts-list/index.js";
import { ShortsEditor } from "@/widgets/shorts-editor/index.js";

export default {
  components: { ShortsList, ShortsEditor },
  setup() {
    onMounted(() => {
      fetchYoutubeStatus()
        .then((y) => {
          youtubeStatus.value = y;
        })
        .catch(() => {});
    });
    return { nav };
  },
  template: `<section class="shorts">
    <ShortsList :filter="nav.route.filter" :pid="nav.route.pid"/>
    <div><ShortsEditor v-if="nav.route.pid" :key="nav.route.pid" :pid="nav.route.pid"/><div v-else class="card muted">왼쪽에서 영상을 고르세요.</div></div>
  </section>`,
};
