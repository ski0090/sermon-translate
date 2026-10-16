// 음성 단계: 목소리와 기본 속도, 음성 만들기, 영상과 함께 미리 듣기, 문장별로 들어 보고 속도·앞 쉼 바꾸기와 다시 만들기
import {computed,inject,ref} from "./vendor/vue.esm-browser.prod.js";
import {api} from "./lib.js";
import {SentenceList,Edit} from "./work-review.js";

const VOICES=["F1","F2","F3","F4","F5","M1","M2","M3","M4","M5"];

export default {
  components:{SentenceList,Edit},
  setup(){
    const W=inject("W"),d=computed(()=>W.d),sel=ref(null),sample=ref(false);
    const done=computed(()=>d.value.sentences.filter(s=>s.tts).length),total=computed(()=>d.value.sentences.length);
    const over=computed(()=>W.plan.filter(p=>p.overflow||p.fixed_overflow).length);
    const running=computed(()=>!!(d.value.job&&d.value.job.running));
    async function setting(body){try{await api(W.P("/settings"),"POST",body);}catch(e){alert(e.message);}await W.reload();}
    function voice(e){
      if(done.value&&!confirm("목소리를 바꾸면 모든 문장의 음성을 다시 만듭니다. 계속할까요?")){e.target.value=d.value.settings.voice;return;}
      setting({voice:e.target.value});
    }
    function listen(){sample.value=true;const a=W.play("/api/voice-sample/"+sel.value.value);a.oncanplay=a.onerror=()=>{sample.value=false;};}
    return {W,d,sel,sample,done,total,over,running,VOICES,setting,voice,listen,make:()=>W.startJob("tts",{force:done.value>=total.value})};
  },
  template:`<div>
    <h2>음성</h2>
    <div class="card">
      <div class="row"><label>목소리 <select ref="sel" :value="d.settings.voice" @change="voice"><option v-for="v in VOICES" :key="v">{{v}}</option></select></label>
        <button class="small" @click="listen">{{sample?"준비 중…":"들어 보기"}}</button>
        <label>기본 속도 <Edit type="number" step="0.05" min="0.8" max="1.5" style="width:80px" :value="d.settings.speed" @save="v=>setting({speed:+v})"/></label>
        <span class="muted">F는 여성, M은 남성 목소리입니다. 바꾸면 모든 문장의 음성을 다시 만듭니다.</span></div>
      <div class="row"><button class="primary" :disabled="running" @click="make">{{done<total?"음성 만들기 ("+(total-done)+"문장 남음)":"음성 모두 만들어짐 · 다시 만들기"}}</button>
        <span class="stat">{{done}}/{{total}} 문장</span><span v-if="over" class="badge warn">길이 초과 {{over}}문장</span>
        <button class="small" @click="W.setPreview(!W.preview)">{{W.preview?"미리 듣기 끄기":"영상과 함께 미리 듣기"}}</button>
        <span style="flex:1"></span><button class="primary" :disabled="!done" @click="W.go('export')">내보내기로</button></div>
    </div>
    <div class="row"><select v-model="W.filter"><option value="all">전체</option><option value="over">길이 초과만</option><option value="check">확인 필요만</option></select><span class="muted">문장별로 들어 보고 속도나 앞 쉼을 바꾸거나 다시 만들 수 있습니다.</span></div>
    <SentenceList tts/>
  </div>`,
};
