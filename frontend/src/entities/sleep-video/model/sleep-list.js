// 음성 영상 목록(/api/sleep)을 화면 사이에 함께 둔다. 음성 영상 화면은 3초마다, 다른 화면에서는 메뉴가 30초마다 새로 받는다
import { ref } from "vue";

export const sleepList = ref(null);
