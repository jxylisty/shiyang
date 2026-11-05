// 专业模式开关（全局，本机持久化）
// 默认关闭：大众只看「说人话」解读 + 配方做法禁忌；
// 打开后显示入血概率、靶点、网络图、通路富集等研究分析（答辩演示用）
import { ref, watch } from 'vue'

const KEY = 'shiyang_pro_mode_v1'

function load() {
  try { return localStorage.getItem(KEY) === '1' } catch { return false }
}

export const proMode = ref(load())

watch(proMode, (v) => {
  try { localStorage.setItem(KEY, v ? '1' : '0') } catch { /* 存储不可用静默 */ }
})

export function setProMode(v) { proMode.value = !!v }
