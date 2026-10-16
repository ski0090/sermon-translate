// 스케줄 달력과 고른 날 카드: 달을 넘기고, 날짜를 누르면 고르고(Shift를 누르면 그 사이의 날을 모두), 이 달 주말을 한 번에 고른다.
// 지난날은 고를 수 없고, 따로 정한 날은 파랗게, 주간 사용량이 초기화되는 날은 그 시각을 보인다. 고른 날의 값을 저장하면 고르기를 비우고 saved
import { computed, reactive } from "vue";
import { TOOLS } from "@/entities/ai-tool/index.js";
import { dayKey, resetDays, monthCells } from "@/entities/schedule/index.js";
import { DaysForm } from "@/features/schedule-edit/index.js";

export default {
  components: { DaysForm },
  props: ["d"],
  emits: ["saved"],
  setup(props, { emit }) {
    const now = new Date(),
      cal = reactive({ y: now.getFullYear(), m: now.getMonth() });
    const sel = reactive(new Set());
    let last = null;
    const resets = computed(() => resetDays(props.d));
    const cells = computed(() =>
      props.d ? monthCells(props.d, cal.y, cal.m, resets.value) : [],
    );
    function month(dm) {
      if (dm === 0) {
        cal.y = now.getFullYear();
        cal.m = now.getMonth();
        return;
      }
      cal.m += dm;
      if (cal.m < 0) {
        cal.m = 11;
        cal.y--;
      }
      if (cal.m > 11) {
        cal.m = 0;
        cal.y++;
      }
    }
    function clickDay(c, e) {
      if (c.blank || c.past) return;
      if (e.shiftKey && last) {
        const [a, b] = [last, c.k].sort();
        for (let t = new Date(a + "T12:00"); ; t.setDate(t.getDate() + 1)) {
          const kk = dayKey(t.getFullYear(), t.getMonth(), t.getDate());
          if (kk > b) break;
          sel.add(kk);
        }
      } else if (sel.has(c.k)) sel.delete(c.k);
      else sel.add(c.k);
      last = c.k;
    }
    const weekends = () =>
      cells.value.forEach((c) => {
        if (!c.blank && !c.past && (c.wd === 0 || c.wd === 6)) sel.add(c.k);
      });
    const days = computed(() => [...sel].sort());
    function saved(v) {
      sel.clear();
      emit("saved", v);
    }
    return {
      cal,
      sel,
      cells,
      month,
      clickDay,
      weekends,
      days,
      saved,
      TOOLS,
    };
  },
  template: `<div class="card" style="margin-top:16px">
      <div class="row" style="justify-content:space-between;margin:0">
        <span class="row" style="margin:0"><button class="small" @click="month(-1)">◀</button><strong style="min-width:7em;text-align:center">{{cal.y}}년 {{cal.m+1}}월</strong><button class="small" @click="month(1)">▶</button><button class="small" @click="month(0)">이번 달</button></span>
        <span class="row" style="margin:0"><button class="small" @click="weekends">이 달 주말 고르기</button><span class="muted"><span class="badge" style="background:var(--accent2);color:var(--accent)">파란 날</span>은 따로 정한 날</span></span>
      </div>
      <div class="cal">
        <div v-for="(w,i) in '일월화수목금토'" :key="w" class="cw" :class="{sun:i===0,sat:i===6}">{{w}}</div>
        <div v-for="c in cells" :key="c.k" class="cd" :class="c.blank?'blank':{sun:c.wd===0,sat:c.wd===6,past:c.past,today:c.today,set:c.set,sel:sel.has(c.k)}" @click="clickDay(c,$event)">
          <template v-if="!c.blank">
            <div class="cdn">{{c.day}} <span v-if="c.today" class="badge ok">오늘</span></div>
            <div class="cdv"><template v-if="c.tool==='claude'">Claude</template><b v-else style="color:#047857">{{TOOLS[c.tool]}}</b><br>5시간 {{c.lim.five_hour}}%<br>주간 {{c.lim.seven_day}}%</div>
            <div v-if="c.reset" class="cdr" title="Claude 주간 사용량이 초기화되는 시각">↻ 주간 초기화 {{c.reset}}</div>
          </template>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <span v-if="!days.length" class="muted">날짜를 누르면 고릅니다. Shift를 누른 채 누르면 그 사이의 날을 모두 고릅니다. 고른 날의 한도를 정하고 "적용"을 누르세요.</span>
      <DaysForm v-else :d="d" :days="days" @saved="saved" @clear="sel.clear()"/>
    </div>`,
};
