import { ref } from 'vue'

const MAX_CHUNK_LEN = 120
const DEFAULT_RATE = 0.92
const DEFAULT_PITCH = 1

/** 当前正在朗读的实例 id；未在朗读时为 null */
export const speakingId = ref(null)

let activeToken = 0
let queue = []
let currentUtterance = null
let cachedVoice = null
let listenersBound = false

/** 判断当前运行环境是否支持浏览器 speechSynthesis */
export function isSpeechSupported() {
  return (
    typeof window !== 'undefined' &&
    'speechSynthesis' in window &&
    typeof window.SpeechSynthesisUtterance === 'function' &&
    typeof window.speechSynthesis?.speak === 'function' &&
    typeof window.speechSynthesis?.cancel === 'function'
  )
}

function pickZhVoice() {
  if (!isSpeechSupported()) return null
  try {
    const voices = window.speechSynthesis.getVoices?.() || []
    if (!voices.length) return cachedVoice
    const zhVoices = voices.filter((v) => /^zh/i.test(v.lang || ''))
    if (!zhVoices.length) {
      cachedVoice = null
      return null
    }
    cachedVoice =
      zhVoices.find((v) => /^zh[-_]?cn$/i.test(v.lang || '') && v.localService) ||
      zhVoices.find((v) => /^zh[-_]?cn$/i.test(v.lang || '')) ||
      zhVoices.find((v) => v.localService) ||
      zhVoices[0]
    return cachedVoice
  } catch {
    return null
  }
}

function handlePageHide() {
  stopSpeak()
}

function ensureListeners() {
  if (listenersBound || !isSpeechSupported()) return
  listenersBound = true
  try {
    const synth = window.speechSynthesis
    if (typeof synth.addEventListener === 'function') {
      synth.addEventListener('voiceschanged', pickZhVoice)
    } else if ('onvoiceschanged' in synth) {
      synth.onvoiceschanged = pickZhVoice
    }
    pickZhVoice()
    window.addEventListener('pagehide', handlePageHide)
  } catch {
    /* 老 WebView 事件挂载受限时静默 */
  }
}

if (typeof window !== 'undefined') {
  ensureListeners()
}

/** 朗读前清洗：去掉 markdown 符号（# * ` >）、链接 URL 与多余空白 */
export function cleanSpeakText(raw) {
  let s = String(raw ?? '')
  // 图片语法 ![alt](url) -> alt；链接语法 [text](url) -> text
  s = s.replace(/!\[([^\]]*)\]\((?:https?:\/\/|\/)[^)]*\)/gi, '$1')
  s = s.replace(/\[([^\]]+)\]\((?:https?:\/\/|\/)[^)]*\)/gi, '$1')
  // 去掉裸 URL
  s = s.replace(/https?:\/\/[^\s)\]>」】）》"'`]+/gi, '')
  // 去掉围栏代码块标记与 markdown 符号 # * ` >
  s = s.replace(/```[a-zA-Z0-9_-]*\s*/g, '')
  s = s.replace(/[#*`>]+/g, '')
  // 统一换行并压缩多余空白
  s = s.replace(/\r\n?/g, '\n')
  s = s
    .split('\n')
    .map((line) => line.replace(/[ \t\u00A0]+/g, ' ').trim())
    .filter(Boolean)
    .join('\n')
  return s.trim()
}

/** 长文本按句号/问号/感叹号/换行切段，超长无标点句兜底按逗号/分号再切 */
function splitSpeakChunks(text) {
  const lines = text.split(/\n+/)
  const chunks = []
  for (const line of lines) {
    const trimmedLine = line.trim()
    if (!trimmedLine) continue
    const sentences = trimmedLine.match(/[^。？！?!]+[。？！?!]*/g) || [trimmedLine]
    for (const s of sentences) {
      const sentence = s.trim()
      if (!sentence) continue
      if (sentence.length <= MAX_CHUNK_LEN) {
        chunks.push(sentence)
        continue
      }
      const clauses = sentence.match(/[^；;，,]+[；;，,]*/g) || [sentence]
      let buf = ''
      for (const c of clauses) {
        const clause = c.trim()
        if (!clause) continue
        if (buf && buf.length + clause.length > MAX_CHUNK_LEN) {
          chunks.push(buf)
          buf = ''
        }
        if (clause.length > MAX_CHUNK_LEN) {
          if (buf) {
            chunks.push(buf)
            buf = ''
          }
          for (let i = 0; i < clause.length; i += MAX_CHUNK_LEN) {
            chunks.push(clause.slice(i, i + MAX_CHUNK_LEN))
          }
        } else {
          buf += clause
        }
      }
      if (buf) chunks.push(buf)
    }
  }
  return chunks
}

function speakNext(token) {
  if (token !== activeToken) return
  if (!queue.length) {
    currentUtterance = null
    speakingId.value = null
    return
  }

  const chunk = queue.shift()
  try {
    const synth = window.speechSynthesis
    const u = new window.SpeechSynthesisUtterance(chunk)
    // 持有当前实例引用，规避部分 Chromium 内核在播放中途被 GC 导致 onend 不触发的问题
    currentUtterance = u

    const voice = cachedVoice || pickZhVoice()
    u.lang = voice?.lang || 'zh-CN'
    if (voice) u.voice = voice
    u.rate = DEFAULT_RATE
    u.pitch = DEFAULT_PITCH

    u.onend = () => {
      if (token !== activeToken) return
      if (currentUtterance === u) currentUtterance = null
      speakNext(token)
    }
    u.onerror = () => {
      if (token !== activeToken) return
      stopSpeak()
    }

    if (synth.paused) synth.resume?.()
    synth.speak(u)
  } catch {
    if (token === activeToken) stopSpeak()
  }
}

/** 立即停止当前朗读并清空队列与状态 */
export function stopSpeak() {
  activeToken += 1
  queue = []
  currentUtterance = null
  speakingId.value = null
  if (!isSpeechSupported()) return
  try {
    window.speechSynthesis.cancel()
  } catch {
    /* 静默 */
  }
}

/** 朗读指定文本并绑定实例 id；新朗读会先 cancel 旧朗读 */
export function speak(text, id) {
  ensureListeners()
  if (!isSpeechSupported()) return false

  const cleaned = cleanSpeakText(text)
  if (!cleaned) {
    stopSpeak()
    return false
  }

  const chunks = splitSpeakChunks(cleaned)
  if (!chunks.length) {
    stopSpeak()
    return false
  }

  stopSpeak()
  const token = activeToken
  queue = chunks
  speakingId.value = id ?? cleaned
  speakNext(token)
  return true
}
