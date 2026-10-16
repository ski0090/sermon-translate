// 문장 한 줄(정리와 검수, 음성 단계): 자막 그림과 읽은 글을 나란히 보고 고치고, 나누고 합치고, 확인 필요를 지운다.
// 고친 칸은 놓는 순간 저장한다. 음성 단계(tts)에서는 속도·앞 쉼과 음성 다시 만들기가 더 보인다
import { computed, ref } from "vue";
import { fmt } from "@/shared/lib/index.js";
import { EditField } from "@/shared/ui/index.js";
import { useWork } from "@/entities/project/index.js";
import { diffParts, edited } from "@/entities/sentence/index.js";
import {
  saveSentence,
  deleteSentence,
  splitSentence,
  mergeSentence,
  regenerateVoice,
} from "../api/sentence.js";

export default {
  props: { s: Object, pl: Object, cur: Boolean, tts: Boolean },
  components: { EditField },
  setup(props) {
    const W = useWork(),
      regen = ref(false);
    const isEdited = computed(() => edited(props.s));
    const diff = computed(() =>
      isEdited.value ? diffParts(props.s.ai, props.s.raw) : [],
    );
    const preview = computed(
      () => props.s.reading_auto || props.s.text.replace(/["'“”‘’]/g, ""),
    );
    const cap = (cid) => W.d.captions[cid];
    // 고친 뒤에는 실패해도 프로젝트를 다시 받는다
    async function run(call) {
      try {
        await call();
      } catch (e) {
        alert(e.message);
      }
      await W.reload();
    }
    const sid = () => props.s.id;
    return {
      W,
      regen,
      isEdited,
      diff,
      preview,
      cap,
      fmt,
      save: (body) => run(() => saveSentence(W.pid, sid(), body)),
      split: (cid) => run(() => splitSentence(W.pid, sid(), +cid)),
      merge: () => run(() => mergeSentence(W.pid, sid())),
      del() {
        if (confirm("이 문장을 지울까요? 음성도 만들지 않습니다."))
          run(() => deleteSentence(W.pid, sid()));
      },
      async regenerate() {
        regen.value = true;
        try {
          await regenerateVoice(W.pid, sid());
        } catch (e) {
          alert(e.message);
        }
        regen.value = false;
        await W.reload();
      },
    };
  },
  template: `<div class="sent" :class="{cur}" :id="'s'+s.id">
    <div class="crops">
      <div v-for="(cid,i) in s.caps" :key="cid" class="cap"><img loading="lazy" :src="W.P('/crop/'+cap(cid).crop)" :title="fmt(cap(cid).start)" @click="W.seek(cap(cid).start)"><button v-if="i>0" class="small" @click="split(cid)">여기서 나누기</button></div>
    </div>
    <div>
      <div class="row" style="margin:0 0 4px"><span class="time">{{fmt(s.start)}} – {{fmt(s.end)}}</span>
        <span v-if="s.check" class="badge warn">확인 필요</span>
        <span v-if="isEdited" class="badge">자동 수정됨</span>
        <span v-if="pl&&pl.fixed_overflow" class="badge bad">고정 지점 초과</span><span v-else-if="pl&&pl.overflow" class="badge warn">길이 초과</span>
        <span v-if="pl&&pl.tempo>1.001" class="badge">{{pl.tempo.toFixed(2)}}배속</span>
        <span style="flex:1"></span>
        <button class="small" @click="W.seek(s.start)">▶ 영상</button><button v-if="s.tts" class="small" @click="W.play(W.P('/tts/'+s.tts))">♪ 음성</button>
      </div>
      <EditField area :value="s.text" @save="v=>save({text:v.trim()})"/>
      <div v-if="s.check&&s.note" class="muted" style="font-size:12px">확인: {{s.note}} <button class="small" @click="save({check:false})">확인함</button></div>
      <div v-if="isEdited" class="diff muted" style="font-size:12px">읽은 글: <template v-for="p in diff"><mark v-if="p.m">{{p.t}}</mark><template v-else>{{p.t}}</template></template> <button class="small" @click="save({text:s.raw})">되돌리기</button></div>
      <div class="reading">읽는 글: <EditField :value="s.reading" :placeholder="preview" @save="v=>save({reading:v.trim()||null})"/></div>
      <div class="tools"><button class="small" @click="merge">다음 문장과 합치기</button><button class="small" @click="del">삭제</button>
        <template v-if="tts">
          <label class="muted">속도 <EditField type="number" step="0.05" min="0.8" max="1.5" style="width:70px" :value="s.speed" :placeholder="String(W.d.settings.speed)" @save="v=>save({speed:v?+v:null})"/></label>
          <label class="muted">앞 쉼(초) <EditField type="number" step="0.1" min="0" max="5" style="width:64px" :value="s.pause||0" @save="v=>save({pause:+v||0})"/></label>
          <button class="small" :disabled="regen" @click="regenerate">{{regen?"만드는 중…":"음성 다시 만들기"}}</button>
        </template>
      </div>
    </div>
  </div>`,
};
