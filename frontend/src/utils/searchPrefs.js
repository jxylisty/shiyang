// 搜索偏好（最近搜索 + 快搜词）：SearchBox 下拉与独立搜索页共用
const HISTORY_KEY = 'shiyang_search_history_v1'
const HISTORY_MAX = 8

// 快搜词：体质/场景/药材高频词（静态）
export const QUICK_WORDS = ['气虚', '润肺', '助眠', '枸杞', '菊花', '换季调理', '阴虚', '祛湿']

export function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { return [] }
}

export function saveHistory(kw) {
  const kwTrim = (kw || '').trim()
  if (!kwTrim) return loadHistory()
  const list = loadHistory().filter(x => x !== kwTrim)
  list.unshift(kwTrim)
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, HISTORY_MAX))) } catch { /* 存储不可用静默 */ }
  return list.slice(0, HISTORY_MAX)
}

export function clearHistory() {
  try { localStorage.removeItem(HISTORY_KEY) } catch { /* ignore */ }
}
