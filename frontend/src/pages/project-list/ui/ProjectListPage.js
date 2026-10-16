// 프로젝트 목록 화면(#/projects/<단계>): 새 프로젝트(구글 드라이브, 유튜브 연결), 자동 진행, 드라이브 영상 목록과 다른 프로젝트.
// 왼쪽 메뉴에서 고른 단계(nav.route.filter)의 영상만 보이고, 목록은 2초마다 새로 받는다(바뀐 줄만 다시 그린다)
import { computed, onMounted, onUnmounted, ref } from "vue";
import { every } from "@/shared/lib/index.js";
import { nav } from "@/shared/router/index.js";
import { library, fetchLibrary } from "@/entities/library/index.js";
import { youtubeStatus, fetchYoutubeStatus } from "@/entities/youtube/index.js";
import { fetchBatch } from "@/entities/batch/index.js";
import { DriveModal, fetchDriveStatus } from "@/features/drive-import/index.js";
import { YoutubeMetaModal } from "@/features/youtube-meta/index.js";
import { NewProjectCard } from "@/widgets/new-project/index.js";
import { BatchPanel } from "@/widgets/batch-panel/index.js";
import { LibraryList } from "@/widgets/library-list/index.js";

export default {
  components: {
    NewProjectCard,
    BatchPanel,
    LibraryList,
    DriveModal,
    YoutubeMetaModal,
  },
  setup() {
    const all = computed(() => nav.route.filter === "all"),
      f = computed(() => nav.route.filter);
    const batch = ref(null),
      drive = ref(null),
      modal = ref(null);
    // 드라이브 영상 목록, 유튜브 연결, 자동 진행(전체를 볼 때만)을 함께 받는다. refresh면 드라이브 목록을 새로 읽게 한다
    async function load(refresh) {
      const [lib, yt, b] = await Promise.all([
        fetchLibrary(refresh),
        fetchYoutubeStatus().catch(() => youtubeStatus.value),
        all.value ? fetchBatch().catch(() => batch.value) : batch.value,
      ]);
      library.value = lib;
      youtubeStatus.value = yt;
      batch.value = b;
    }
    let stop;
    onMounted(() => {
      stop = every(2000, () => load());
      fetchDriveStatus()
        .then((s) => {
          drive.value = s;
        })
        .catch(() => {});
    });
    onUnmounted(() => stop());
    return { all, f, batch, drive, modal, load };
  },
  template: `<section class="start">
    <NewProjectCard v-if="all" :drive="drive" @open="modal=$event"/>
    <BatchPanel v-if="all&&batch" :b="batch" @changed="load()"/>
    <LibraryList :filter="f" @reload="load"/>
    <DriveModal v-if="modal==='drive'" @close="modal=null"/>
    <YoutubeMetaModal v-if="modal==='ytmeta'" @close="modal=null"/>
  </section>`,
};
