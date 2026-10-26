import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

const authApi = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})
authApi.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('shiyang_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// ---- 公开接口 ----
export const getQuestionnaire = () => api.get('/constitution/questionnaire')
export const submitQuiz = (answers) => api.post('/constitution/submit', { answers })
export const getConstitution = (code) => api.get(`/constitution/${code}`)
export const listRecipes = (params) => api.get('/recipes', { params })
export const getRecipe = (id) => api.get(`/recipes/${id}`)
export const listHerbs = (q) => api.get('/herbs', { params: q ? { q } : {} })
export const listCompounds = (minProb = 0.5, limit = 200) => api.get('/compounds', { params: { min_prob: minProb, limit } })
export const getStats = () => api.get('/stats')
export const getExposure = (id) => api.get(`/recipes/${id}/exposure`)
export const getNetwork = (id) => api.get(`/recipes/${id}/network`)
export const getEvidenceChain = (id) => api.get(`/recipes/${id}/chain`)
export const getPathways = (id) => api.get(`/recipes/${id}/pathways`)
export const compareRecipes = (a, b) => api.get('/recipes/compare', { params: { a, b } })

// ---- 全局搜索 ----
export const globalSearch = (q, limit) => api.get('/search', { params: limit ? { q, limit } : { q } })

// ---- AI 助手对话（SSE，POST；后端 RAG 检索库内资料后流式回答） ----
export function streamAssistantChat(question, onCitations, onDelta, onDone, onError,
                                    { history = [], constitutionCode = null } = {}) {
  const ctrl = new AbortController()
  fetch('/api/v1/assistant/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: ctrl.signal,
    body: JSON.stringify({ question, history, constitution_code: constitutionCode }),
  }).then(async (resp) => {
    if (!resp.ok || !resp.body) {
      let msg = 'AI 服务不可用'
      try { msg = (await resp.json()).detail || msg } catch { /* ignore */ }
      onError(msg)
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = '', full = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') { onDone(full); return }
        try {
          const j = JSON.parse(data)
          if (j.error) { onError(j.error); return }
          if (j.citations) { onCitations(j.citations, j.no_context) }
          if (j.delta) { full += j.delta; onDelta(full) }
        } catch { /* 忽略半包 */ }
      }
    }
    onDone(full)
  }).catch((e) => { if (e.name !== 'AbortError') onError(e.message) })
  return () => ctrl.abort()
}

// ---- 我的茶罐（反向配伍） ----
export const getPantryMaterials = () => api.get('/pantry/materials')
export const pantryMatch = (owned, constitution) => api.post('/pantry/match', { owned, constitution })

// ---- 慢病安全滤镜 ----
export const getSafetyProfiles = () => api.get('/safety/profiles')
export const safetyCheck = (recipeId, profile) => api.get(`/safety/check/${recipeId}`, { params: { profile } })
export const safetyCheckBatch = (recipeIds, profile) => api.post('/safety/check-batch', { recipe_ids: recipeIds, profile })

// ---- 证据分级与溯源 ----
export const getEvidenceLevels = () => api.get('/evidence/levels')
export const getEvidence = (recipeId) => api.get(`/evidence/recipe/${recipeId}`)

// ---- 入血概率可解释 ----
export const getExplainCompound = (name) => api.get('/explain/compound', { params: { name } })
export const getExplainRecipe = (recipeId) => api.get(`/explain/recipe/${recipeId}`)

// ---- 开放数据 API ----
export const getOpenIndex = () => api.get('/open')

// ---- 周期报告 ----
export const getCycleReport = (days = 21) => authApi.get('/report/cycle', { params: { days } })

// ---- 节气推荐 ----
export const getTermCurrent = (count = 4) => api.get('/term/current', { params: { count } })

// ---- 「为你推荐」（千人千面） ----
export const getMyRecommend = (count = 4) => authApi.get('/me/recommend', { params: { count } })
export const guestRecommend = (judged, count = 4) => api.post('/constitution/recommend', { judged, count })

// ---- 本地体质暂存（未登录也能驱动推荐；登录用户后端有档案为准） ----
const LOCAL_CONST_KEY = 'shiyang_constitution_local_v1'
export function saveLocalConstitution(judged, transformed) {
  try {
    localStorage.setItem(LOCAL_CONST_KEY, JSON.stringify({
      judged, transformed, ts: Date.now(),
    }))
  } catch { /* 存储不可用静默 */ }
}
export function getLocalConstitution() {
  try { return JSON.parse(localStorage.getItem(LOCAL_CONST_KEY) || 'null') } catch { return null }
}

// ---- AI（SSE 用 fetch；key 可为空 → 后端回放预生成解读） ----
export function streamAIReport(recipeId, key, onDelta, onDone, onError, provider = 'deepseek') {
  const kq = key ? `key=${encodeURIComponent(key)}&` : ''
  const url = `/api/v1/recipes/${recipeId}/ai-report?${kq}provider=${provider}`
  const ctrl = new AbortController()
  fetch(url, { signal: ctrl.signal }).then(async (resp) => {
    if (!resp.ok || !resp.body) {
      // 预生成缺失（404）或其他错误，取后端 detail 提示
      let msg = 'AI 服务不可用'
      try { msg = (await resp.json()).detail || msg } catch { /* ignore */ }
      onError(msg)
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = '', full = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') { onDone(full); return }
        try {
          const j = JSON.parse(data)
          if (j.error) { onError(j.error); return }
          if (j.delta) { full += j.delta; onDelta(full, j.source) }
        } catch { /* 忽略半包 */ }
      }
    }
    onDone(full)
  }).catch((e) => { if (e.name !== 'AbortError') onError(e.message) })
  return () => ctrl.abort()
}

// ---- 用户系统 ----
export const register = (username, password, nickname) => api.post('/auth/register', { username, password, nickname })
export const login = (username, password) => api.post('/auth/login', { username, password })
export const getMe = () => authApi.get('/me')
export const saveRecord = (judged, transformed, answers, memberId = null) => authApi.post('/constitution/records', { judged, transformed, answers, member_id: memberId })
export const listRecords = () => authApi.get('/constitution/records')

// ---- 家庭成员档案 ----
export const listFamilyMembers = () => authApi.get('/family/members')
export const addFamilyMember = (name, relation, color) => authApi.post('/family/members', { name, relation, color })
export const removeFamilyMember = (id) => authApi.delete(`/family/members/${id}`)
export const addFavorite = (id) => authApi.post(`/favorites/${id}`)
export const removeFavorite = (id) => authApi.delete(`/favorites/${id}`)
export const listFavorites = () => authApi.get('/favorites')

// ---- 饮用打卡 ----
export const doCheckin = (id) => authApi.post(`/checkins/${id}`)
export const undoCheckin = (id) => authApi.delete(`/checkins/${id}`)
export const listCheckins = () => authApi.get('/checkins')

export const isLoggedIn = () => !!localStorage.getItem('shiyang_token')
export const logout = () => { localStorage.removeItem('shiyang_token'); localStorage.removeItem('shiyang_user') }
export const saveSession = (data) => {
  localStorage.setItem('shiyang_token', data.token)
  localStorage.setItem('shiyang_user', JSON.stringify({ id: data.id, username: data.username, nickname: data.nickname }))
}
export const currentUser = () => {
  try { return JSON.parse(localStorage.getItem('shiyang_user') || 'null') } catch { return null }
}

// ---- 配料图片（构建期预拉取到 /img/materials/{name}.jpg，见 scripts/fetch_material_images.py） ----
// 同一食材的异名映射到同一张图（方子录入用名 ≠ 拉图脚本用名时兜底）
const MAT_IMG_ALIAS = {
  枣: '大枣', 铁皮石斛: '石斛', 猪瘦肉: '猪肉', 排骨: '猪骨', 猪脊骨: '猪骨',
  当归: '党参', 天冬: '麦冬', 地黄: '玉竹', 猪肚: '猪骨',
}
export const matImg = (name) =>
  `/img/materials/${encodeURIComponent(MAT_IMG_ALIAS[name] || name)}.jpg`

// ---- 浏览历史（纯本地，未登录可用） ----
const HISTORY_KEY = 'shiyang_history_v1'
const HISTORY_MAX = 20

export function pushHistory(item) {
  try {
    const list = getHistory().filter(x => x.id !== item.id)
    list.unshift({ ...item, ts: Date.now() })
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, HISTORY_MAX)))
  } catch { /* 存储不可用时静默 */ }
}
export function getHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { return [] }
}
export function clearHistory() {
  try { localStorage.removeItem(HISTORY_KEY) } catch { /* ignore */ }
}
