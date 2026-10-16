// 로그인 진행 상자: 진행 중이면 아무 기기에서 열 주소와 넣을 코드(주소가 아직 없으면 도구가 낸 글)와 "로그인 취소", 끝났으면 성공·실패
import { computed } from "vue";
import { runToolAction } from "../model/run.js";

export default {
  props: ["x"],
  emits: ["reload"],
  setup(props, { emit }) {
    return {
      lg: computed(() => props.x.login),
      cancel: () => runToolAction(emit, props.x.tool, "cancel", true),
    };
  },
  template: `<div v-if="lg&&(lg.running||lg.error||lg.ok)" class="tllogin">
        <template v-if="lg.running"><b>로그인 진행 중</b> — 아래 주소를 아무 기기의 브라우저에서 열고 코드를 넣으세요.<br>
          <a v-if="lg.url" :href="lg.url" target="_blank">{{lg.url}}</a><template v-else>주소를 기다리는 중…</template><template v-if="lg.code"> · 코드 <b style="font-size:16px;letter-spacing:1px">{{lg.code}}</b></template></template>
        <span v-else-if="lg.ok" class="badge ok">로그인했습니다</span>
        <template v-else><span class="badge bad">로그인 실패</span> {{lg.error||""}}</template>
        <pre v-if="lg.lines&&lg.lines.length&&!lg.url" class="tlcode">{{lg.lines.join("\\n")}}</pre>
        <button v-if="lg.running" class="small" @click="cancel">로그인 취소</button>
      </div>`,
};
