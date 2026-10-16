// 설정 > AI 도구 화면(#/tools): Claude, Codex, Antigravity마다 설치·로그인·플랜, 사용 켜기/끄기, 모델 고르기, 지금 쓰는 모델,
// 로그인·로그아웃·연결 시험, 모델별 사용 가능 여부와 쓴 한도. Codex 로그인 중이나 한도를 읽는 중에만 2초마다 새로 읽고,
// 고르는 중인 모델 칸은 덮지 않는다
import { onMounted, onUnmounted, ref } from "vue";
import { every } from "@/shared/lib/index.js";
import { TOOLS, fetchTools } from "@/entities/ai-tool/index.js";
import { ToolCard } from "@/widgets/tool-card/index.js";

export default {
  components: { ToolCard },
  setup() {
    const r = ref(null),
      err = ref(null);
    // 상태를 읽지 못하면 화면에 알리고, "상태 다시 읽기"로 다시 읽는다
    const load = async (fresh) => {
      try {
        r.value = await fetchTools(fresh);
        err.value = null;
      } catch (e) {
        err.value = e.message;
      }
    };
    let stop;
    onMounted(() => {
      load(true);
      // Codex 로그인 중이거나 Antigravity 한도를 뒤에서 읽는 중에만 자주 새로 읽는다
      stop = every(2000, async () => {
        if (
          r.value &&
          r.value.tools.some(
            (x) => (x.login && x.login.running) || x.usage_busy,
          )
        )
          await load();
      });
    });
    onUnmounted(() => stop());
    return { r, err, load, TOOLS };
  },
  template: `<section class="toolsv">
    <div class="card" style="margin-bottom:12px"><strong>AI 도구</strong>
      <div class="muted">자막 읽기, 문장 정리, 쇼츠 후보 고르기에 쓰는 AI 도구입니다. 끈 도구는 쓰지 않고, 스케줄에서 끈 도구로 정한 날은 켜진 도구로 대신합니다. 모델을 비워 두면 도구의 기본 모델을 씁니다.</div>
      <div class="row"><template v-if="r">오늘 자동 작업 도구: <b>{{r.today?TOOLS[r.today]:"없음(모든 도구가 꺼짐)"}}</b></template> <button class="small" @click="load(true)">상태 다시 읽기</button></div>
      <div v-if="err" class="err" style="margin:6px 0 0">도구 상태를 읽지 못했습니다: {{err}}</div>
    </div>
    <div v-if="!r&&!err" class="card muted">도구 상태를 확인하는 중…</div>
    <template v-else><ToolCard v-for="x in r.tools" :key="x.tool" :x="x" @reload="load"/></template>
  </section>`,
};
