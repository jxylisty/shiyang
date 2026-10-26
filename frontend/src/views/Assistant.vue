<script setup>
// 「问一问」AI 助手对话页（T3-11）：RAG 限定库内资料 + 强制引用编号
// 引用卡可点进详情；历史存 localStorage 最多 20 轮；体质快捷注入用本地暂存的测评结果
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { streamAssistantChat, getLocalConstitution } from '../api'

const router = useRouter()
const HISTORY_KEY = 'shiyang_assistant_history_v1'
const HISTORY_MAX_ROUNDS = 20

const msgs = ref([])        // [{role:'user'|'assistant', content, citations?, no_context?, streaming?}]
const input = ref('')
const sending = ref(false)
const errTip = ref('')
const listRef = ref(null)
const citationsByRound = ref({})   // 本轮流式中的引用（随 citations 事件更新）

// 体质快捷注入：本地暂存的测评结果（登录用户后端档案为准，这里只是快捷入口）
const localConst = getLocalConstitution()
const constNames = localConst?.judged?.combined?.length
  ? localConst.judged.combined.map((c) => ({ code: c, name: c.replace('质', '') }))
  : []
const injectConst = ref(false)
const enabledConst = () => constNames.find((c) => c.code === injectCode.value)
const injectCode = ref(constNames[0]?.code || '')

const QUICK_QS = ['嗓子干喝什么茶', '助眠方子有哪些', '枸杞有什么成分', '气虚体质适合什么']

let abort = null

function load() {
  try { msgs.value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { msgs.value = [] }
}
function save() {
  try {
    const trimmed = msgs.value.slice(-HISTORY_MAX_ROUNDS * 2)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed))
  } catch { /* 存储不可用静默 */ }
}
function clearAll() {
  if (msgs.value.length && !window.confirm('清空全部对话记录？')) return
  msgs.value = []
  try { localStorage.removeItem(HISTORY_KEY) } catch { /* ignore */ }
}

function scrollBottom() {
  nextTick(() => { listRef.value?.scrollTo({ top: listRef.value.scrollHeight, behavior: 'smooth' }) })
}

function send(text) {
  const q = (text ?? input.value).trim()
  if (!q || sending.value) return
  input.value = ''
  errTip.value = ''
  msgs.value.push({ role: 'user', content: q })
  const ai = { role: 'assistant', content: '', citations: [], streaming: true }
  msgs.value.push(ai)
  sending.value = true
  scrollBottom()

  // 上下文带最近 2 轮（4 条），历史里不含本轮
  const prior = msgs.value.slice(0, -2).filter((m) => m.content)
  const history = prior.slice(-4).map((m) => ({ role: m.role, content: m.content }))

  const stop = streamAssistantChat(
    q,
    (cites, noCtx) => { ai.citations = cites || []; ai.no_context = noCtx; scrollBottom() },
    (full) => { ai.content = full; scrollBottom() },
    () => {
      ai.streaming = false
      sending.value = false
      if (!ai.content) {
        ai.content = errTip.value || '（这次没有取得回答，请稍后再试）'
        if (!errTip.value) errTip.value = ''
      }
      save()
    },
    (err) => {
      ai.streaming = false
      sending.value = false
      ai.content = ai.content || ''
      errTip.value = typeof err === 'string' ? err : 'AI 服务异常'
      save()
    },
    { history, constitutionCode: injectConst.value ? injectCode.value : null },
  )
  abort = stop
}

function stopStream() {
  abort?.()
  sending.value = false
  const last = msgs.value[msgs.value.length - 1]
  if (last?.streaming) { last.streaming = false; save() }
}

// 引用卡跳转：方子 → 详情，成分 → 词典；药材暂无详情页则跳药材图鉴
function goCite(c) {
  if (c.kind === 'recipe') router.push(`/recipes/${c.ref_id}`)
  else if (c.kind === 'compound') router.push(`/compounds/${encodeURIComponent(c.title)}`)
  else router.push({ path: '/herbs', query: { h: c.title } })
}

// **加粗** 拆段渲染（不用 v-html 防注入）；流式期间未闭合的 ** 尾段按普通文本
function segments(text) {
  const parts = String(text || '').split('**')
  const odd = (parts.length - 1) % 2 === 1
  const out = []
  parts.forEach((p, i) => {
    if (!p) return
    out.push({ t: p, b: i % 2 === 1 && !(odd && i === parts.length - 1) })
  })
  return out
}

onMounted(() => { load(); scrollBottom() })
</script>

<template>
  <div class="page as-page">
    <div class="as-head card">
      <div class="as-title">
        <AppIcon name="chat" :size="17" :stroke-width="2" /> 问一问
        <button v-if="msgs.length" class="as-clear" @click="clearAll">清空记录</button>
      </div>
      <p class="as-sub">基于本平台方子库与药材库的食养问答，回答附出处引用；AI 生成，仅供参考。</p>
      <!-- 体质快捷注入：本地暂存过测评结果才显示 -->
      <div v-if="constNames.length" class="as-const" @click.prevent>
        <label class="as-switch">
          <input type="checkbox" v-model="injectConst" />
          <span>以{{ constNames.map((c) => c.name).join('/') }}身份提问</span>
        </label>
      </div>
    </div>

    <div class="as-list" ref="listRef">
      <!-- 空会话：快捷提问 -->
      <div v-if="!msgs.length" class="card as-empty">
        <p>试试这样问：</p>
        <div class="as-chips">
          <button v-for="qq in QUICK_QS" :key="qq" class="as-chip" @click="send(qq)">{{ qq }}</button>
        </div>
      </div>

      <div v-for="(m, i) in msgs" :key="i" class="as-row" :class="m.role">
        <div v-if="m.role === 'assistant'" class="as-avatar"><AppIcon name="leaf" :size="13" /></div>
        <div class="as-bubble" :class="{ me: m.role === 'user' }">
          <span v-if="m.role === 'assistant'" class="as-tag"><AppIcon name="sparkles" :size="10" /> AI 生成</span>
          <div class="as-text" :class="{ typing: m.streaming }">
            <template v-for="(seg, si) in segments(m.content || (m.streaming ? '正在检索库内资料…' : ''))" :key="si">
              <b v-if="seg.b">{{ seg.t }}</b><template v-else>{{ seg.t }}</template>
            </template>
          </div>
          <div v-if="errTip && m.role === 'assistant' && i === msgs.length - 1" class="as-err">{{ errTip }}</div>
          <!-- 引用卡（方子/药材/成分），流式开始前就能看到 -->
          <div v-if="m.citations?.length" class="as-cites">
            <button v-for="c in m.citations" :key="c.id" class="as-cite pressable" @click="goCite(c)">
              <span class="ac-id">{{ c.id }}</span>
              <span class="ac-main">
                <span class="ac-title">{{ c.title }}</span>
                <span class="ac-sub">{{ c.sub }}<template v-if="c.detail"> · {{ c.detail }}</template></span>
              </span>
              <AppIcon name="chevron" :size="12" />
            </button>
          </div>
        </div>
      </div>

      <div v-if="sending" class="as-stop">
        <button class="as-stop-btn" @click="stopStream">停止生成</button>
      </div>
    </div>

    <div class="as-input card">
      <textarea v-model="input" rows="1" placeholder="问问食养方子/药材/成分…（Enter 发送）"
                @keydown.enter.exact.prevent="send()" />
      <button class="as-send" :disabled="sending || !input.trim()" @click="send()">
        <AppIcon name="chevron" :size="15" :stroke-width="2.4" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.as-page { max-width: 760px; margin: 0 auto; padding-bottom: 20px; }
.as-head { padding: 14px 16px; margin-bottom: 12px; }
.as-title { display: flex; align-items: center; gap: 7px; font-size: 16px; font-weight: 700; color: var(--ink-900); font-family: var(--font-serif); }
.as-title svg { color: var(--green-600); }
.as-clear { margin-left: auto; border: none; background: none; color: var(--ink-400); font-size: 12px; cursor: pointer; font-family: inherit; }
.as-clear:hover { color: var(--cinnabar); }
.as-sub { font-size: 12px; color: var(--ink-400); margin: 6px 0 0; line-height: 1.6; }
.as-const { margin-top: 10px; }
.as-switch { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--ink-600); cursor: pointer; }
.as-switch input { accent-color: var(--green-600); }

.as-list { display: flex; flex-direction: column; gap: 14px; min-height: 40vh; }
.as-empty { padding: 26px 18px; text-align: center; color: var(--ink-400); font-size: 13.5px; }
.as-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 12px; }
.as-chip { border: 1px solid var(--green-100); background: var(--green-50); color: var(--ink-600); font-size: 13px; font-family: inherit; padding: 6px 14px; border-radius: 16px; cursor: pointer; }
.as-chip:hover { border-color: var(--green-600); color: var(--green-text); }

.as-row { display: flex; gap: 8px; }
.as-row.user { justify-content: flex-end; }
.as-avatar {
  flex-shrink: 0; width: 26px; height: 26px; border-radius: 50%;
  background: var(--green-50); border: 1px solid var(--green-100);
  display: inline-flex; align-items: center; justify-content: center; color: var(--green-600);
  margin-top: 2px;
}
.as-bubble {
  max-width: 78%; background: var(--card-bg, #fff); border: 1px solid var(--card-border);
  border-radius: 10px; padding: 10px 13px; font-size: 14px; line-height: 1.75; color: var(--ink-900);
  box-shadow: 0 1px 4px rgba(30, 40, 33, .05);
}
.as-bubble.me { background: var(--green-50); border-color: var(--green-100); }
.as-tag { display: inline-flex; align-items: center; gap: 3px; font-size: 10px; color: var(--ink-400); margin-bottom: 4px; }
.as-text { white-space: pre-wrap; word-break: break-word; }
.as-text.typing::after { content: '▍'; color: var(--green-600); animation: blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.as-err { margin-top: 6px; font-size: 12px; color: var(--cinnabar); }

.as-cites { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; border-top: 1px dashed var(--card-border); padding-top: 10px; }
.as-cite {
  display: flex; align-items: center; gap: 9px; text-align: left; width: 100%;
  border: 1px solid var(--card-border); background: transparent; border-radius: 8px;
  padding: 7px 10px; cursor: pointer; font-family: inherit;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.as-cite:hover { border-color: var(--green-600); background: var(--green-50); }
.ac-id { flex-shrink: 0; font-size: 10px; font-weight: 700; color: var(--green-text); background: var(--green-50); border: 1px solid var(--green-100); border-radius: 4px; padding: 1px 5px; }
.as-cite:hover .ac-id { background: #fff; }
.ac-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.ac-title { font-size: 13px; font-weight: 600; color: var(--ink-900); font-family: var(--font-serif); }
.ac-sub { font-size: 11px; color: var(--ink-400); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.as-cite svg { flex-shrink: 0; color: var(--ink-400); }

.as-stop { display: flex; justify-content: center; }
.as-stop-btn { border: 1px solid var(--card-border); background: var(--card-bg, #fff); color: var(--ink-400); font-size: 12px; font-family: inherit; padding: 5px 16px; border-radius: 14px; cursor: pointer; }
.as-stop-btn:hover { color: var(--cinnabar); border-color: var(--cinnabar); }

.as-input { display: flex; align-items: flex-end; gap: 8px; padding: 10px 12px; position: sticky; bottom: 12px; margin-top: 12px; }
.as-input textarea {
  flex: 1; border: none; resize: none; outline: none; background: transparent;
  font-family: inherit; font-size: 14px; line-height: 1.5; color: var(--ink-900); max-height: 96px;
}
.as-send {
  flex-shrink: 0; width: 34px; height: 34px; border-radius: 50%; border: none; cursor: pointer;
  background: var(--green-700); color: #fdfaf1; display: inline-flex; align-items: center; justify-content: center;
}
.as-send:disabled { opacity: .4; cursor: not-allowed; }
.as-send svg { transform: rotate(90deg); margin-left: -1px; }
</style>
