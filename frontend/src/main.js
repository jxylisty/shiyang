import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import Vant from 'vant'
import 'vant/lib/index.css'

// 启动即应用本机设置（字号/主题），跨页面不丢
const FONT_KEYS = ['standard', 'large', 'xlarge']
const font = localStorage.getItem('shiyang_fontscale')
document.documentElement.dataset.fontsize = FONT_KEYS.includes(font) ? font : 'standard'
const dark = localStorage.getItem('shiyang_theme') === 'dark'
document.documentElement.classList.toggle('van-theme-dark', dark)
document.documentElement.dataset.theme = dark ? 'dark' : 'light'

createApp(App).use(router).use(Vant).mount('#app')
