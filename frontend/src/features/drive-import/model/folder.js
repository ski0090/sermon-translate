// 드라이브 창에서 보던 폴더. 창을 닫았다 다시 열어도 그대로다
import { reactive } from "vue";

export const folder = reactive({ path: "", shared: false });
