// 全局适老化字号与「长辈关怀模式」状态管理（本机持久化，跨顶栏与「我的」页实时同步）
import { ref, computed, watch } from 'vue'
import { showSuccessToast } from 'vant'
import { setProMode } from './proMode'

export const FONT_KEYS = ['standard', 'large', 'xlarge']
export const FONT_LABELS = { standard: '标准', large: '大', xlarge: '特大' }

const STORE_KEY = 'shiyang_fontscale'

function loadInitial() {
  try {
    const v = localStorage.getItem(STORE_KEY)
    return FONT_KEYS.includes(v) ? v : 'standard'
  } catch {
    return 'standard'
  }
}

export const fontScale = ref(loadInitial())
export const isElderMode = computed(() => fontScale.value !== 'standard')

function syncDom(v) {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.fontsize = FONT_KEYS.includes(v) ? v : 'standard'
  }
}

watch(fontScale, (v) => {
  const safe = FONT_KEYS.includes(v) ? v : 'standard'
  try {
    localStorage.setItem(STORE_KEY, safe)
  } catch { /* 存储不可用静默 */ }
  syncDom(safe)
}, { immediate: true })

export function setFontScale(v) {
  if (!FONT_KEYS.includes(v)) return
  fontScale.value = v
}

export function toggleElderMode() {
  if (isElderMode.value) {
    fontScale.value = 'standard'
    showSuccessToast('已切回标准字号')
  } else {
    fontScale.value = 'large'
    // 开启长辈版时自动收起专业科研图表，优先呈现大白话解读与适宜/禁忌提醒
    setProMode(false)
    showSuccessToast('已开启长辈大字版')
  }
}
