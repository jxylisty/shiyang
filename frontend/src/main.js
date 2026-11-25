import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import Vant from 'vant'
// 用到的样式集中加载一次，主题覆盖保持最后。
import 'vant/es/empty/style/index.mjs'
import 'vant/es/list/style/index.mjs'
import 'vant/es/popup/style/index.mjs'
import 'vant/es/progress/style/index.mjs'
import 'vant/es/search/style/index.mjs'
import 'vant/es/toast/style/index.mjs'
import 'vant/es/dialog/style/index.mjs'
import './style.css'
import './utils/fontScale'

// 启动即应用本机暗色主题，跨页面不丢（字号由 utils/fontScale 自动同步）
const dark = localStorage.getItem('shiyang_theme') === 'dark'
document.documentElement.classList.toggle('van-theme-dark', dark)
document.documentElement.dataset.theme = dark ? 'dark' : 'light'
document.documentElement.classList.toggle('native-app', import.meta.env.MODE === 'app')

createApp(App).use(router).use(Vant).mount('#app')
