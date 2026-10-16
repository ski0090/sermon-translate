// 날짜별 사용 카드(최근 14일): 도구마다 호출 수(실패 수)와 토큰(보낸 것 / 받은 것). 이 앱이 부른 것만 센다
import { tok } from "@/entities/usage/index.js";

export default {
  props: ["d"],
  setup() {
    return { tok };
  },
  template: `<div class="card"><strong>날짜별 사용 (최근 14일)</strong>
        <template v-if="d.days.length">
          <table class="uvtab">
            <tr><th>날짜</th><th v-for="(n,t) in d.names" :key="t">{{n}}</th></tr>
            <tr v-for="[day,v] in d.days" :key="day"><td>{{day}}</td>
              <td v-for="(n,t) in d.names" :key="t"><template v-if="v[t]">{{v[t].calls}}회<span v-if="v[t].fails" style="color:var(--bad)"> (실패 {{v[t].fails}})</span><div class="muted">{{tok(v[t].in)}} / {{tok(v[t].out)}}</div></template><span v-else class="muted">-</span></td>
            </tr>
          </table>
          <div class="muted">호출 수(실패 수)와 토큰(보낸 것 / 받은 것). 이 앱이 부른 것만 셉니다.</div>
        </template>
        <div v-else class="muted">아직 기록이 없습니다.</div>
      </div>`,
};
