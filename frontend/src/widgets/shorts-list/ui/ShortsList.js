// 쇼츠 화면 왼쪽: 쇼츠를 만들 수 있는 영상 목록(고른 상태 filter만)과 자동 후보 켜기. 5초마다 새로 받고, 누르면 그 영상(pid)을 고른다
import { computed, onMounted, onUnmounted, ref } from "vue";
import { every } from "@/shared/lib/index.js";
import { openShorts } from "@/shared/router/index.js";
import {
  SH_STAGES,
  shStage,
  shortsBadge,
  shortsList,
  fetchShortsList,
} from "@/entities/shorts/index.js";
import { AutoSuggestToggle } from "@/features/shorts-create/index.js";

export default {
  components: { AutoSuggestToggle },
  props: ["filter", "pid"],
  setup(props) {
    const auto = ref(false);
    let stop;
    onMounted(() => {
      stop = every(5000, async () => {
        const r = await fetchShortsList();
        shortsList.value = r.items;
        auto.value = !!r.auto;
      });
    });
    onUnmounted(() => stop());
    const f = computed(() => props.filter);
    const items = computed(() =>
      (shortsList.value || []).filter(
        (x) => f.value === "all" || shStage(x) === f.value,
      ),
    );
    const title = computed(() =>
      f.value === "all"
        ? "쇼츠"
        : "쇼츠 · " + SH_STAGES.find((x) => x[0] === f.value)[1],
    );
    return {
      shorts: shortsList,
      auto,
      items,
      title,
      badge: shortsBadge,
      pick: (dir) => openShorts(f.value, dir),
    };
  },
  template: `<div class="card side">
      <strong>{{title}}</strong>
      <div class="muted">문장 정리가 끝난 영상에서 AI가 쇼츠 구간(30~60초)과 제목·강조 구절을 고르고, 원본 음성에 한국어 자막을 크게 박은 세로 영상(1080×1920)을 만듭니다. 결과는 "한국어 더빙/쇼츠" 폴더와 구글 드라이브에 저장됩니다.</div>
      <AutoSuggestToggle :auto="auto"/>
      <ul class="plist">
        <li v-for="x in items" :key="x.dir" :class="{sel:x.dir===pid}" @click="pick(x.dir)"><div>{{x.name}}</div><span class="badge" :class="badge(x).cls">{{badge(x).text}}</span></li>
        <li v-if="!items.length" class="muted">{{!shorts?"불러오는 중…":shorts.length?"이 상태의 영상이 없습니다.":"문장 정리까지 끝난 영상이 없습니다."}}</li>
      </ul>
    </div>`,
};
