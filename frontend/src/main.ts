import { createApp } from "vue";
import { createPinia } from "pinia";
import { ElButton, ElTag } from "element-plus";
import "element-plus/es/components/button/style/css";
import "element-plus/es/components/tag/style/css";
import "./style.css";
import "./styles/workspace.css";
import App from "./App.vue";
import router from "./router";

document.documentElement.classList.remove("dark");
createApp(App)
  .use(createPinia())
  .use(router)
  .component("ElButton", ElButton)
  .component("ElTag", ElTag)
  .mount("#app");
