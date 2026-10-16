// 고른 영상의 쇼츠(쇼츠 화면 오른쪽): 머리 카드(프로젝트 열기, 직접 추가, Claude 후보와 그 상태)와 쇼츠 카드들.
// 처음에 문장까지 받고, 그 뒤로는 2.5초마다 문장 없이 상태만 받는다. 카드와 단추가 넘긴 요청(act)을 보내고 받은 상태를 반영한다
import { computed, onMounted, onUnmounted, ref } from "vue";
import { every } from "@/shared/lib/index.js";
import { openProject } from "@/shared/router/index.js";
import { fetchShorts } from "@/entities/shorts/index.js";
import { ShortCard } from "@/features/short-edit/index.js";
import {
  AddShortButton,
  SuggestButton,
} from "@/features/shorts-create/index.js";

export default {
  props: ["pid"],
  components: { ShortCard, AddShortButton, SuggestButton },
  setup(props) {
    const d = ref(null),
      err = ref(null);
    const take = (v) => {
      d.value = { ...v, sentences: d.value.sentences };
    };
    let stop;
    onMounted(async () => {
      try {
        d.value = await fetchShorts(props.pid);
      } catch (e) {
        err.value = e.message;
        return;
      }
      stop = every(2500, async () => take(await fetchShorts(props.pid, true)));
    });
    onUnmounted(() => stop && stop());
    async function act(call) {
      try {
        take(await call());
      } catch (e) {
        alert(e.message);
      }
    }
    const g = computed(() => (d.value && d.value.suggest) || {});
    return { d, err, g, act, open: () => openProject(props.pid) };
  },
  template: `<div v-if="err" class="err">{{err}}</div>
    <div v-else-if="!d" class="card muted">불러오는 중…</div>
    <template v-else>
      <div class="card" style="margin-bottom:12px">
        <div class="row" style="justify-content:space-between">
          <div><strong>{{d.name}}</strong> <span class="muted">{{d.items.length?"쇼츠 "+d.items.length+"개":""}}</span></div>
          <span class="row"><button class="small" @click="open">프로젝트 열기</button><AddShortButton :pid="pid" @act="act"/>
            <SuggestButton :pid="pid" :more="!!d.items.length" :busy="g.status==='queued'||g.status==='running'" @act="act"/></span>
        </div>
        <div class="muted">제목과 구간, 강조를 고치면 왼쪽에 미리 보기 그림이 나오고, "다시 만들기"를 눌러야 영상에 반영됩니다. 강조는 글을 마우스로 고른 뒤 "선택한 글 강조"를 누르고, 노란 글을 누르면 뺍니다. 문장을 누르면 그 장면을 봅니다.</div>
        <div v-if="g.status==='running'" class="job" style="margin:8px 0 0"><span>{{g.msg||"Claude가 고르는 중"}}</span></div>
        <div v-else-if="g.status==='queued'" class="muted" style="margin-top:6px">후보 고르기 대기 중{{g.ahead?" (앞에 "+g.ahead+"개)":""}}{{g.msg?" · "+g.msg:""}}</div>
        <div v-else-if="g.status==='error'" class="err" style="margin:8px 0 0">후보를 고르지 못했습니다: {{g.error}}</div>
      </div>
      <ShortCard v-for="it in d.items" :key="it.id" :it="it" :sentences="d.sentences" :pid="pid" @act="act"/>
      <div v-if="!d.items.length" class="card muted">아직 쇼츠가 없습니다. "Claude로 후보 만들기"를 누르거나 "직접 추가"로 구간을 정하세요.</div>
    </template>`,
};
