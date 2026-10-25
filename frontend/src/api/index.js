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
export const getStats = () => api.get('/stats')
export const getExposure = (id) => api.get(`/recipes/${id}/exposure`)
export const getNetwork = (id) => api.get(`/recipes/${id}/network`)

// ---- AI（SSE 用 fetch，key 不落库不进 axios 默认头） ----
export function streamAIReport(recipeId, key, onDelta, onDone, onError, provider = 'deepseek') {
  const url = `/api/v1/recipes/${recipeId}/ai-report?key=${encodeURIComponent(key)}&provider=${provider}`
  const ctrl = new AbortController()
  fetch(url, { signal: ctrl.signal }).then(async (resp) => {
    if (!resp.ok || !resp.body) { onError('AI 服务不可用'); return }
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
          if (j.delta) { full += j.delta; onDelta(full) }
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
export const saveRecord = (judged, transformed, answers) => authApi.post('/constitution/records', { judged, transformed, answers })
export const listRecords = () => authApi.get('/constitution/records')
export const addFavorite = (id) => authApi.post(`/favorites/${id}`)
export const removeFavorite = (id) => authApi.delete(`/favorites/${id}`)
export const listFavorites = () => authApi.get('/favorites')

export const isLoggedIn = () => !!localStorage.getItem('shiyang_token')
export const logout = () => { localStorage.removeItem('shiyang_token'); localStorage.removeItem('shiyang_user') }
export const saveSession = (data) => {
  localStorage.setItem('shiyang_token', data.token)
  localStorage.setItem('shiyang_user', JSON.stringify({ id: data.id, username: data.username, nickname: data.nickname }))
}
export const currentUser = () => {
  try { return JSON.parse(localStorage.getItem('shiyang_user') || 'null') } catch { return null }
}
