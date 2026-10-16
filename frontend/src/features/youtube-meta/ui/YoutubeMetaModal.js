// 유튜브 영상 설명과 해시태그 창. 미리 보기는 서버의 yt_meta와 같은 규칙(해시태그를 설명 끝에 붙인다)
import { computed, onMounted, reactive } from "vue";
import { ModalCard } from "@/shared/ui/index.js";
import { fetchYoutubeSettings, saveYoutubeSettings } from "../api/settings.js";

export default {
  components: { ModalCard },
  emits: ["close"],
  setup(_, { emit }) {
    const f = reactive({
      description: "",
      hashtags: "",
      shorts_title: "",
      shorts_description: "",
      sleep_title: "",
      sleep_description: "",
    });
    onMounted(async () => {
      const m = await fetchYoutubeSettings();
      for (const k in f) f[k] = m[k] ?? "";
    });
    const preview = computed(() => {
      const tags = f.hashtags
        .split(/[\s,]+/)
        .map((t) => t.replace(/^#+/, ""))
        .filter(Boolean);
      return (
        f.description
          .split("{이름}")
          .join("218 선생이 아닌 구세주 예수")
          .trim() +
        (tags.length ? "\n\n" + tags.map((t) => "#" + t).join(" ") : "")
      );
    });
    async function save() {
      try {
        await saveYoutubeSettings({ ...f });
        emit("close");
      } catch (e) {
        alert(e.message);
      }
    }
    return { f, preview, save };
  },
  template: `<ModalCard>
    <h2 style="margin-top:0">유튜브 영상 설명과 해시태그</h2>
    <label>설명 ({이름}은 영상 이름으로 바뀝니다)</label>
    <textarea v-model="f.description" rows="5" style="width:100%"></textarea>
    <label>해시태그 (띄어쓰기로 구분, 설명 끝에 붙고 태그로도 들어갑니다. 앞의 3개가 제목 위에 보입니다)</label>
    <input v-model="f.hashtags" style="width:100%">
    <label>미리 보기</label>
    <pre class="muted" style="white-space:pre-wrap;background:var(--bg);padding:8px;border-radius:6px;margin:0">{{preview}}</pre>
    <label>쇼츠 제목 ({제목}은 쇼츠 화면 위의 제목 두 줄, {이름}은 영상 이름)</label>
    <input v-model="f.shorts_title" style="width:100%">
    <label>쇼츠 설명 ({링크}는 유튜브에 올린 전체 영상 주소. 전체 영상이 아직 없으면 그 줄은 빠집니다. 해시태그는 #Shorts와 위의 해시태그가 붙습니다)</label>
    <textarea v-model="f.shorts_description" rows="3" style="width:100%"></textarea>
    <label>음성 영상 제목 ({이름}은 영상 이름)</label>
    <input v-model="f.sleep_title" style="width:100%">
    <label>음성 영상 설명 ({링크}는 유튜브에 올린 더빙 영상 주소. 없으면 그 줄은 빠집니다)</label>
    <textarea v-model="f.sleep_description" rows="3" style="width:100%"></textarea>
    <div class="muted" style="margin-top:6px">새로 올리는 영상에만 적용됩니다. 이미 유튜브에 있던 영상의 설명은 바꾸지 않습니다.</div>
    <div class="row" style="justify-content:flex-end;margin-top:12px"><button @click="$emit('close')">닫기</button><button class="primary" @click="save">저장</button></div>
  </ModalCard>`,
};
