// 유튜브 연결 상태(/api/youtube/status: 연결 여부, 채널, 재생목록, 로그인 진행)를 화면 사이에 함께 둔다
import { computed, ref } from "vue";

export const youtubeStatus = ref(null);
export const youtubeConnected = computed(
  () => !!(youtubeStatus.value && youtubeStatus.value.connected),
);
