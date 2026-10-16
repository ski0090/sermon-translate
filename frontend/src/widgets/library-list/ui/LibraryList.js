// 구글 드라이브 영상 목록 카드: 고른 단계(filter)의 드라이브 영상과, 드라이브에 없는 다른 프로젝트.
// 줄을 누르면 프로젝트를 열고, 아직 프로젝트가 없으면 물어본 뒤 내려받기를 시작한다. 새로 받을 일이 생기면 reload(새로고침이면 true)
import { computed } from "vue";
import { fmt } from "@/shared/lib/index.js";
import { openProject } from "@/shared/router/index.js";
import {
  JobBar,
  jobName,
  progressText,
  projStage,
  stageName,
} from "@/entities/project/index.js";
import { library, libState } from "@/entities/library/index.js";
import { BATCH_ITEM } from "@/entities/batch/index.js";
import { YoutubeCell } from "@/features/youtube-upload/index.js";
import { importLibraryItem } from "@/features/drive-import/index.js";

export default {
  components: { JobBar, YoutubeCell },
  props: ["filter"],
  emits: ["reload"],
  setup(props, { emit }) {
    const all = computed(() => props.filter === "all"),
      f = computed(() => props.filter);
    const rows = computed(() =>
      library.value
        ? library.value.items
            .map((it) => ({ it, st: libState(it) }))
            .filter((r) => all.value || r.st.stage === f.value)
        : [],
    );
    const others = computed(() =>
      library.value
        ? library.value.others.filter(
            (p) => all.value || projStage(p) === f.value,
          )
        : [],
    );
    const sum = computed(() => {
      const lib = library.value;
      if (!lib || !lib.items.length) return "";
      if (!all.value) return `${rows.value.length}개`;
      const n = (k) =>
        lib.items.filter((it) => libState(it).group === k).length;
      return `${lib.items.length}개 · 완료 ${n("done")} · 진행 중 ${n("run")} · 시작 전 ${n("todo")}`;
    });
    async function openItem(it) {
      if (it.project) return openProject(it.project.dir);
      if (it.importing) return;
      if (await importLibraryItem(it)) emit("reload");
    }
    return {
      lib: library,
      all,
      f,
      rows,
      others,
      sum,
      auto: BATCH_ITEM,
      openItem,
      openProject,
      stageName,
      projStage,
      progressText,
      jobName,
      fmt,
    };
  },
  template: `<div class="card" style="margin-top:16px">
      <div class="row" style="justify-content:space-between;margin:0"><strong>구글 드라이브 {{lib?lib.root:""}} 폴더{{all?"":" · "+stageName(f)}}</strong><span class="row" style="margin:0"><span class="muted">{{sum}}</span><button class="small" @click="$emit('reload',true)">새로고침</button></span></div>
      <ul class="plist">
        <li v-if="lib&&lib.error" class="err">{{lib.error}}</li>
        <template v-else-if="rows.length">
          <li v-for="r in rows" :key="r.it.path" @click="openItem(r.it)">
            <div class="pleft"><div>{{r.it.name}} <span class="badge" :class="r.st.cls">{{r.st.label}}</span><template v-if="auto[r.it.batch]&&!(r.it.project&&r.it.project.job)"> <span class="badge">{{auto[r.it.batch]}}</span></template></div></div>
            <div class="pright"><JobBar v-if="r.st.job" :job="r.st.job"/><div v-else class="muted" style="text-align:right">{{r.st.text}}</div><YoutubeCell :it="r.it" @changed="$emit('reload')"/></div>
          </li>
        </template>
        <li v-else class="muted">{{!lib||lib.loading?"불러오는 중…":all?"영상이 없습니다.":"이 단계의 영상이 없습니다."}}</li>
      </ul>
      <div v-if="others.length" style="margin-top:16px"><strong>다른 프로젝트</strong>
        <ul class="plist">
          <li v-for="p in others" :key="p.dir" @click="openProject(p.dir)">
            <div class="pleft"><div>{{p.name}} <span class="badge" :class="{ok:p.job}">{{p.job?"진행 중 · "+jobName(p.job):p.exported?"완료":stageName(projStage(p))}}</span></div><div class="muted ellipsis">{{p.drive||p.video||""}}</div></div>
            <div class="pright"><JobBar v-if="p.job" :job="p.job"/><div v-else class="muted" style="text-align:right">{{progressText(p)}}</div><div class="muted" style="text-align:right">{{p.duration?fmt(p.duration):""}} · {{new Date(p.updated*1000).toLocaleString("ko-KR")}}</div></div>
          </li>
        </ul>
      </div>
    </div>`,
};
