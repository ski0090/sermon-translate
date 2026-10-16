// 쇼츠를 만들 수 있는 영상 목록(/api/shorts의 items)을 화면 사이에 함께 둔다. 쇼츠 화면은 5초마다, 다른 화면에서는 메뉴가 30초마다 새로 받는다
import { ref } from "vue";

export const shortsList = ref(null);
