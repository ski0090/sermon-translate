// AI 도구 하나의 카드: 사용 켜기, 설치 안내(설치되지 않았으면), 로그인·플랜·버전, 지금 쓰는 모델과 모델 고르기,
// 모델별 사용 가능 여부와 쓴 한도 표, Fable 이어 하기 안내, 로그인 진행, 연결 시험·로그인·로그아웃과 마지막 시험 결과.
// 무엇을 바꾸면 reload(fresh면 서버가 다시 확인)
import { computed } from "vue";
import { when } from "@/shared/lib/index.js";
import { modelRows, limitPct, limitColor } from "@/entities/ai-tool/index.js";
import { ToolSwitch, ModelPicker } from "@/features/tool-setup/index.js";
import {
  TestButton,
  LoginButtons,
  LoginBox,
} from "@/features/tool-connection/index.js";

export default {
  components: { ToolSwitch, ModelPicker, TestButton, LoginButtons, LoginBox },
  props: ["x"],
  emits: ["reload"],
  setup(props) {
    const rows = computed(() => modelRows(props.x));
    const count = computed(() => ({
      ok: rows.value.filter((r) => r.v && r.ok === true).length,
      no: rows.value.filter((r) => r.v && r.ok === false).length,
    }));
    return { rows, count, when, pct: limitPct, col: limitColor };
  },
  template: `<div class="card" style="margin-bottom:12px">
    <div class="row" style="justify-content:space-between;margin:0"><strong style="font-size:15px">{{x.name}}</strong>
      <ToolSwitch :x="x" @reload="$emit('reload')"/></div>
    <template v-if="!x.installed">
      <div class="row"><span class="badge warn">설치 안 됨</span></div>
      <div class="muted">서버 PC 터미널에서 설치합니다:</div><pre class="tlcode">{{x.install}}</pre>
      <div class="muted">설치한 뒤 로그인: {{x.login_help}} 그다음 "상태 다시 읽기"를 누르세요.</div>
    </template>
    <template v-else>
      <div class="row">
        <span v-if="x.logged_in===true" class="badge ok">로그인됨</span><span v-else-if="x.logged_in===false" class="badge bad">로그인 안 됨</span><span v-else class="badge">로그인 확인 전</span>
        <span v-if="x.plan" class="badge ok">플랜 {{x.plan}}</span><span v-if="x.account" class="muted">{{x.account}}</span>
        <span class="muted">{{x.version||""}}</span>
      </div>
      <div class="row">지금 쓰는 모델: <b>{{x.active_model||"도구 기본"}}</b><span v-if="x.model" class="badge">직접 고름</span>
        <span class="muted">· 마지막 호출: <template v-if="x.seen_model">{{x.seen_model}}{{x.seen_t?" ("+when(x.seen_t)+" 호출 기준)":""}}</template><template v-else>아직 호출 기록 없음</template></span></div>
      <ModelPicker :x="x" @reload="$emit('reload')"/>
      <details v-if="x.model_info" class="mlist" :open="x.enabled">
        <summary class="muted">모델별 사용 가능 여부와 쓴 한도 (사용 가능 {{count.ok}} · 사용 불가 {{count.no}}){{x.usage_busy?" · 한도를 읽는 중…":""}}</summary>
        <table class="mtab">
          <tr><th>상태</th><th>모델</th><th>쓴 한도</th><th></th></tr>
          <tr v-for="o in rows" :key="o.v">
            <td><span class="badge" :class="o.ok===true?'ok':o.ok===false?'bad':''">{{o.ok===true?"사용 가능":o.ok===false?"사용 불가":"확인 전"}}</span></td>
            <td>{{o.l}}<span v-if="o.v===x.model" class="badge" style="margin-left:4px">고름</span></td>
            <td><span v-for="u in o.limits" :key="u.label" class="mu" :title="u.resets?when(u.resets)+' 초기화':''" :style="{color:col(u.used)}">{{u.label}} {{pct(u.used)}}</span><span v-if="!o.limits.length" class="muted">-</span></td>
            <td class="muted">{{o.why}}</td>
          </tr>
        </table>
      </details>
      <div v-if="x.tool==='claude'" class="muted">사용량을 다 쓰면 Fable로 이어 하기: <b>{{x.fallback?"켜짐":"꺼짐"}}</b><span v-if="x.fallback_now" class="badge ok">지금 Fable로 작업 중</span> (설정 &gt; 스케줄에서 바꿈)</div>
      <div v-if="x.logged_in===false" class="muted">로그인: {{x.login_help}}</div>
      <div v-if="x.tool==='claude'" class="muted">Claude 로그아웃은 이 PC의 Claude Code도 같이 로그아웃되어 화면에서는 하지 않습니다. 쓰지 않으려면 "사용"을 끄세요.</div>
      <LoginBox :x="x" @reload="$emit('reload',$event)"/>
      <div class="row">
        <TestButton :x="x" @reload="$emit('reload',$event)"/>
        <LoginButtons :x="x" @reload="$emit('reload',$event)"/>
        <span v-if="x.tested" class="muted">연결 시험 {{when(x.tested.t)}}: <span v-if="x.tested.ok" style="color:var(--ok)">성공</span><span v-else style="color:var(--bad)">{{x.tested.msg}}</span></span>
      </div>
    </template>
  </div>`,
};
