// 음성 영상 목록 카드: 고른 상태(filter)의 영상마다 상태, 진행 막대, 만들기·멈추기, 재생(줄 아래에 영상)·내려받기, 유튜브.
// 목록을 새로 받아도 재생 중인 영상은 끊기지 않는다(같은 줄을 다시 그리기만 한다)
import { computed, ref } from "vue";
import {
  svStage,
  svBusy,
  svPct,
  svInfo,
  sleepPath,
} from "@/entities/sleep-video/index.js";
import { RenderButton } from "@/features/sleep-render/index.js";
import { SleepYoutubeCell } from "@/features/sleep-upload/index.js";

export default {
  components: { RenderButton, SleepYoutubeCell },
  props: ["d", "filter"],
  emits: ["changed"],
  setup(props) {
    const open = ref(null);
    const items = computed(() =>
      props.d.items.filter(
        (x) => props.filter === "all" || svStage(x) === props.filter,
      ),
    );
    return {
      open,
      items,
      busy: svBusy,
      pct: svPct,
      info: svInfo,
      P: sleepPath,
    };
  },
  template: `<div class="card" style="margin-top:16px"><ul class="plist">
      <li v-for="x in items" :key="x.dir">
        <div class="pleft">
          <div>{{x.name}}
            <template v-if="x.status==='rendering'"><span class="badge ok">만드는 중</span> <span class="muted">{{x.msg||""}}</span></template>
            <span v-else-if="x.status==='queued'" class="badge">대기{{x.ahead?" (앞에 "+x.ahead+"편)":""}}</span>
            <template v-else-if="x.status==='error'"><span class="badge bad">실패</span> <span class="muted" style="color:var(--bad)">{{(x.error||"").slice(0,150)}}</span></template>
            <template v-else-if="x.has_file"><span class="badge ok">완성</span> <span class="muted">{{info(x)}}</span></template>
            <span v-else class="badge">아직 없음</span>
            <span v-if="!x.voice_done" class="badge warn" title="음성이 없는 문장은 빠집니다">음성 {{x.tts}}/{{x.sentences}}</span>
          </div>
          <div v-if="x.status==='rendering'" class="pjob" style="justify-content:flex-start;margin-top:4px"><div class="bar"><i :style="{width:pct(x)+'%'}"></i></div><span class="time">{{pct(x)}}%</span></div>
        </div>
        <div class="pright row" style="margin:0;justify-content:flex-end">
          <RenderButton :x="x" @changed="$emit('changed')"/>
          <template v-if="x.has_file"><button class="small" @click="open=open===x.dir?null:x.dir">{{open===x.dir?"닫기":"▶ 재생"}}</button><a :href="P(x,'/video?dl=1')" download>내려받기</a></template>
          <SleepYoutubeCell :x="x" :yt="d.yt" @changed="$emit('changed')"/>
        </div>
        <div v-if="open===x.dir&&x.has_file" style="flex-basis:100%"><video controls preload="metadata" :src="P(x,'/video?v='+Math.round(x.rendered||0))"></video></div>
      </li>
      <li v-if="!items.length" class="muted">해당하는 영상이 없습니다.</li>
    </ul></div>`,
};
