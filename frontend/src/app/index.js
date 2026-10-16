// 화면(Vue, 빌드 없음)의 시작: 주소를 읽고 화면 틀(App)을 #app에 붙인다.
// 층은 FSD를 따른다: app → pages → widgets → features → entities → shared(아래 층만 부른다)
import { createApp } from "vue";
import { startRouter } from "./router/index.js";
import App from "./ui/App.js";

startRouter();
createApp(App).mount("#app");
