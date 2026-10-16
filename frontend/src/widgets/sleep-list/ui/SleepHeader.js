// 음성 영상 화면 위 카드: 설명, 아직 없는 영상 모두 만들기, 내보내기 뒤 자동으로 만들기
import { computed } from "vue";
import { svStage } from "@/entities/sleep-video/index.js";
import {
  RenderAllButton,
  AutoRenderToggle,
} from "@/features/sleep-render/index.js";

export default {
  components: { RenderAllButton, AutoRenderToggle },
  props: ["d"],
  emits: ["changed"],
  setup(props) {
    // 아직 음성 영상이 없고 만들고 있지도 않은 영상 수
    const todo = computed(
      () =>
        props.d.items.filter((x) => !x.has_file && svStage(x) !== "making")
          .length,
    );
    return { todo };
  },
  template: `<div class="card">
      <div class="row" style="justify-content:space-between;margin:0"><strong>음성 영상 (자면서 듣는 설교)</strong>
        <RenderAllButton :todo="todo" @changed="$emit('changed')"/></div>
      <div class="muted">원본 화면 대신 어두운 배경에 설교 제목과 소리에 맞춰 움직이는 이퀄라이저를 보여 주고, 소리는 영상 싱크 없이 문장을 원래 속도로 이은 더빙 음성입니다. 한 편씩 만들며 1시간 설교에 약 11분 걸립니다. 다 만들면 구글 드라이브의 결과 폴더에 올립니다.</div>
      <AutoRenderToggle :auto="d.auto"/>
    </div>`,
};
