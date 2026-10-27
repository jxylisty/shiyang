import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import Vant from 'vant'
// 顺序要紧：Vant 的 `:root,:host` 与我们的 `:root` 特异性相同（都是 0,1,0），
// 同特异性下后加载者胜出。style.css 必须放在 vant 之后，
// 否则 --van-primary-color 等主题覆盖会被 Vant 默认值反压（实测解析成默认蓝 #1989fa）。
import 'vant/lib/index.css'
import './style.css'

// 启动即应用本机设置（字号/主题），跨页面不丢
const FONT_KEYS = ['standard', 'large', 'xlarge']
const font = localStorage.getItem('shiyang_fontscale')
document.documentElement.dataset.fontsize = FONT_KEYS.includes(font) ? font : 'standard'
const dark = localStorage.getItem('shiyang_theme') === 'dark'
document.documentElement.classList.toggle('van-theme-dark', dark)
document.documentElement.dataset.theme = dark ? 'dark' : 'light'

createApp(App).use(router).use(Vant).mount('#app')
