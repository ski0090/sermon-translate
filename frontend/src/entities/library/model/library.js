// 드라이브 영상 목록(/api/library)을 화면 사이에 함께 둔다. 프로젝트 목록 화면은 2초마다, 다른 화면에서는 메뉴가 30초마다 새로 받는다
import { ref } from "vue";

export const library = ref(null);
