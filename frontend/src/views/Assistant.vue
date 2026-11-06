<script setup>
// 「问一问」AI 助手对话页（T3-11）：RAG 限定库内资料 + 强制引用编号
// 引用卡可点进详情；历史存 localStorage 最多 20 轮；体质快捷注入用本地暂存的测评结果
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Check } from '@lucide/vue'
import AppIcon from '../components/AppIcon.vue'
import AgentAvatar from '../components/AgentAvatar.vue'
import DisclaimerBanner from '../components/DisclaimerBanner.vue'
import { streamAssistantChat, getLocalConstitution, matImg } from '../api'
import { PHARMACOPOEIA_FUNCTIONS } from '../utils/pharmacopoeiaFunctions'

const router = useRouter()
const HISTORY_KEY = 'shiyang_assistant_history_v1'
const HISTORY_MAX_ROUNDS = 20

const msgs = ref([])        // [{role:'user'|'assistant', content, citations?, no_context?, streaming?, ...}]
const input = ref('')
const sending = ref(false)
const errTip = ref('')
const listRef = ref(null)
const citeImgFailed = ref({})

// 体质快捷注入：本地暂存的测评结果（登录用户后端档案为准，这里只是快捷入口）
// combined 里存的是拼音 code（qixu/xueyu/qiyu/tebing 等），这里转成中文短名
const CONST_SHORT = {
  pinghe: '平和', qixu: '气虚', yangxu: '阳虚', yinxu: '阴虚',
  tanshi: '痰湿', shire: '湿热', qiyu: '气郁', tebing: '特禀', xueyu: '血瘀',
}
const localConst = getLocalConstitution()
const constNames = localConst?.judged?.combined?.length
  ? localConst.judged.combined
      .filter(c => CONST_SHORT[c])
      .map(c => ({ code: c, name: CONST_SHORT[c] }))
  : []
const injectConst = ref(false)
const injectCode = ref(constNames[0]?.code || '')
const enabledConst = () => constNames.find((c) => c.code === injectCode.value)

const QUICK_QS = ['嗓子干喝什么茶', '助眠方子有哪些', '枸杞有什么成分', '气虚体质适合什么']

let abort = null
let tickTimer = null

function clearTick() {
  if (tickTimer) {
    clearInterval(tickTimer)
    tickTimer = null
  }
}

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
    msgs.value = Array.isArray(raw)
      ? raw.map((m) => ({
          ...m,
          streaming: false,
          citationsReady: Boolean(m.citations?.length || m.no_context),
          thinkOpen: false,
        }))
      : []
  } catch {
    msgs.value = []
  }
}

function save() {
  try {
    const trimmed = msgs.value.slice(-HISTORY_MAX_ROUNDS * 2).map((m) => {
      if (m.role !== 'assistant') return { role: m.role, content: m.content }
      return {
        role: 'assistant',
        content: m.content,
        citations: m.citations || [],
        no_context: Boolean(m.no_context),
        ttftSec: m.ttftSec ?? null,
        usedConst: m.usedConst || '',
      }
    })
    localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed))
  } catch { /* 存储不可用静默 */ }
}

function clearAll() {
  if (msgs.value.length && !window.confirm('清空全部对话记录？')) return
  stopStream()
  msgs.value = []
  try { localStorage.removeItem(HISTORY_KEY) } catch { /* ignore */ }
}

function scrollBottom(instant = false) {
  nextTick(() => {
    const el = listRef.value
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: instant ? 'auto' : 'smooth' })
  })
}

// ---- 统计某条回复真实命中的方子 / 药材 / 成分数量（严格基于实测 citations，不编造数字） ----
function citeStats(m) {
  const list = m?.citations || []
  let recipe = 0, herb = 0, compound = 0
  for (const c of list) {
    if (c.kind === 'recipe') recipe++
    else if (c.kind === 'compound') compound++
    else herb++
  }
  const parts = []
  if (recipe) parts.push(`${recipe} 道方子`)
  if (herb) parts.push(`${herb} 味药材`)
  if (compound) parts.push(`${compound} 项成分`)
  return { total: list.length, recipe, herb, compound, summary: parts.join(' · ') }
}

// ---- 思考态动态阶段计算（真实 SSE 节点 + setInterval 时间推进，禁用双 rAF） ----
function thinkingState(m) {
  const stats = citeStats(m)
  const elapsed = m.elapsedMs || 0

  // 阶段 0：尚未收到后端 RAG citations 事件
  if (!m.citationsReady) {
    return {
      key: 'rag-search',
      icon: 'search',
      headline: '正在拆解问题意图，巡检方子与本草库',
      sub: '检索药食同源目录、食养茶饮方与成分归属关系…',
      stepIdx: 0,
    }
  }

  // 已收到 citations 事件，等待大模型首字输出（TTFT 窗口期）
  const sinceCite = Math.max(0, elapsed - (m.citeAtMs || 0))

  if (sinceCite < 1500) {
    if (stats.total > 0) {
      return {
        key: 'rag-locked',
        icon: 'herb',
        headline: `已命中 ${stats.total} 条库内资料，正在比对性味与配伍`,
        sub: `锁定 ${stats.summary}，正在交叉核验关联信息…`,
        stepIdx: 1,
      }
    }
    return {
      key: 'rag-fallback',
      icon: 'book',
      headline: '未检出直接同名条目，正在匹配相近食养参考',
      sub: '正在整理日常调理方向与安全注意事项…',
      stepIdx: 1,
    }
  }

  // 进入大模型深度组织回答阶段：按 2.1s 节拍轮换真实工序描述，让用户持续感知进展
  const pool = []
  if (m.usedConst) {
    pool.push({
      key: 'llm-const',
      icon: 'sparkles',
      headline: `正在结合「${m.usedConst}」体质倾向筛选适宜建议`,
      sub: '优先比对性味温和度、适宜人群与日常饮用频次…',
    })
  } else {
    pool.push({
      key: 'llm-safety',
      icon: 'book',
      headline: '正在核对药典性味归经、适宜人群与禁忌提醒',
      sub: '逐条标注库内引用编号，过滤缺乏依据的说法…',
    })
  }
  if (stats.compound > 0) {
    pool.push({
      key: 'llm-compound',
      icon: 'molecule',
      headline: '正在梳理入血成分预测与靶点参考依据',
      sub: '区分模型预测值与文献记载，转化为通俗食养解读…',
    })
  } else {
    pool.push({
      key: 'llm-brew',
      icon: 'tea',
      headline: '正在提炼配料搭配要点与冲泡调理建议',
      sub: '兼顾日常可操作性与饮食安全边界…',
    })
  }
  pool.push({
    key: 'llm-compose',
    icon: 'sparkles',
    headline: '正在组织条理清晰的食养解答，即将输出',
    sub: stats.total > 0 ? `正在将 ${stats.total} 条库内出处嵌入正文引用…` : '正在审校表述严谨度与健康提示…',
  })

  const idx = Math.min(pool.length - 1, Math.floor((sinceCite - 1500) / 2100))
  return {
    ...pool[idx],
    stepIdx: 2,
  }
}

function formatSec(ms) {
  return `${(Math.max(0, ms || 0) / 1000).toFixed(1)}s`
}

function send(text) {
  const q = (text ?? input.value).trim()
  if (!q || sending.value) return
  input.value = ''
  errTip.value = ''
  clearTick()

  // 上下文带最近 2 轮（4 条），历史里不含本轮
  const prior = msgs.value.filter((m) => m.content)
  const history = prior.slice(-4).map((m) => ({ role: m.role, content: m.content }))

  const activeConst = injectConst.value ? enabledConst() : null
  msgs.value.push({ role: 'user', content: q })
  msgs.value.push({
    role: 'assistant',
    content: '',
    citations: [],
    no_context: false,
    citationsReady: false,
    citeAtMs: 0,
    streaming: true,
    elapsedMs: 0,
    ttftSec: null,
    thinkOpen: false,
    usedConst: activeConst?.name || '',
  })
  // 关键：从 ref 数组中取回响应式 Proxy，确保流式事件实时触发视图刷新
  const ai = msgs.value[msgs.value.length - 1]
  const startedAt = Date.now()

  sending.value = true
  scrollBottom()

  tickTimer = setInterval(() => {
    ai.elapsedMs = Date.now() - startedAt
  }, 100)

  const stop = streamAssistantChat(
    q,
    (cites, noCtx) => {
      ai.citations = cites || []
      ai.no_context = Boolean(noCtx)
      ai.citationsReady = true
      ai.citeAtMs = Date.now() - startedAt
      scrollBottom()
    },
    (full) => {
      if (ai.ttftSec == null && full) {
        ai.ttftSec = Number(((Date.now() - startedAt) / 1000).toFixed(1))
      }
      ai.content = full
      scrollBottom(true)
    },
    () => {
      clearTick()
      if (ai.ttftSec == null) {
        ai.ttftSec = Number(((Date.now() - startedAt) / 1000).toFixed(1))
      }
      ai.streaming = false
      sending.value = false
      if (!ai.content) {
        ai.content = errTip.value || '（这次没有取得回答，请稍后再试）'
        if (!errTip.value) errTip.value = ''
      }
      save()
      scrollBottom()
    },
    (err) => {
      clearTick()
      ai.streaming = false
      sending.value = false
      ai.content = ai.content || ''
      errTip.value = typeof err === 'string' ? err : 'AI 服务异常'
      save()
    },
    { history, constitutionCode: activeConst ? activeConst.code : null },
  )
  abort = stop
}

function stopStream() {
  abort?.()
  clearTick()
  sending.value = false
  const last = msgs.value[msgs.value.length - 1]
  if (last?.streaming) {
    last.streaming = false
    if (!last.content) last.content = '（已手动停止生成）'
    save()
  }
}

function toggleTrace(m) {
  m.thinkOpen = !m.thinkOpen
}

// 引用卡跳转：方子 → 详情，成分 → 词典；药材跳药材图鉴并定位
function goCite(c) {
  if (!c) return
  if (c.kind === 'recipe') router.push(`/recipes/${c.ref_id}`)
  else if (c.kind === 'compound') router.push(`/compounds/${encodeURIComponent(c.title)}`)
  else router.push({ path: '/herbs', query: { h: c.title } })
}

// 引用卡封面图：
// - 方子：从 detail 的「配料：xxx、yyy」里拆出第一味
// - 药材：直接用自身名
// - 成分：无图，用图标兜底
function citeCover(c) {
  if (c.kind === 'herb') return matImg(c.title)
  if (c.kind === 'recipe' && c.detail) {
    const m = c.detail.match(/配料[：:]\s*([^、·]+)/)
    if (m && m[1]) return matImg(m[1].trim())
  }
  return ''
}
function citeIconName(c) {
  if (c.kind === 'recipe') return 'tea'
  if (c.kind === 'compound') return 'molecule'
  return 'herb'
}
function onCiteImgErr(c) { citeImgFailed.value[c.id] = true }

// 药材引用卡若遇到扩容英文 functions，优先映射《中国药典》中文标准功能词并注明出处
function formatCiteDetail(c) {
  if (!c?.detail) return ''
  if (c.kind === 'herb' && /[A-Za-z]{4,}/.test(c.detail)) {
    const entry = PHARMACOPOEIA_FUNCTIONS[c.title]
    if (entry?.fn) return `功效：${entry.fn}`
  }
  return c.detail
}

// **加粗** + [F1]/[H1]/[C1] 引用角标安全拆段渲染（不用 v-html 防注入）
function segments(text, cites = []) {
  const citeMap = new Map((cites || []).map((c) => [c.id, c]))
  const parts = String(text || '').split('**')
  const odd = (parts.length - 1) % 2 === 1
  const out = []

  parts.forEach((p, i) => {
    if (!p) return
    const bold = i % 2 === 1 && !(odd && i === parts.length - 1)
    // 拆分形如 [F12]、[H1]、[C2] 的引用标记
    const tokens = p.split(/(\[[FHC]\d+\])/g)
    for (const tk of tokens) {
      if (!tk) continue
      const m = tk.match(/^\[([FHC]\d+)\]$/)
      if (m && citeMap.has(m[1])) {
        out.push({ t: m[1], cite: citeMap.get(m[1]), b: false })
      } else {
        out.push({ t: tk, b: bold, cite: null })
      }
    }
  })
  return out
}

onMounted(() => { load(); scrollBottom(true) })
onBeforeUnmount(() => { clearTick(); abort?.() })
</script>

<template>
  <div class="page as-page">
    <div class="as-head card">
      <div class="as-head-main">
        <AgentAvatar :size="38" :state="sending ? 'thinking' : 'idle'" />
        <div class="as-head-copy">
          <div class="as-title">
            <span>问一问</span>
            <span class="as-persona-badge">青囊 · 寻证助手</span>
            <button v-if="msgs.length" class="as-clear" @click="clearAll">清空记录</button>
          </div>
          <p class="as-sub">由食养寻证助手「青囊」检索方子库、药典性味与入血成分依据作答；AI 生成，仅供参考。</p>
        </div>
      </div>
      <!-- 体质快捷注入：本地暂存过测评结果才显示 -->
      <div v-if="constNames.length" class="as-const" @click.prevent>
        <label class="as-switch">
          <input type="checkbox" v-model="injectConst" />
          <span>以{{ constNames.map((c) => c.name).join('/') }}体质提问</span>
        </label>
        <p class="as-const-tip">回答会按你的体质倾向推荐更对路的方子</p>
      </div>
    </div>

    <div class="as-list" ref="listRef">
      <!-- 空会话：快捷提问 -->
      <div v-if="!msgs.length" class="card as-empty">
        <div class="as-empty-avatar">
          <AgentAvatar :size="60" state="idle" />
        </div>
        <p class="as-empty-title">你好，我是「青囊」</p>
        <p class="as-empty-sub">食养有据专属寻证助手——每次提问都会先翻阅库内方剂、本草性味与活性成分依据，试试这样问：</p>
        <div class="as-chips">
          <button v-for="qq in QUICK_QS" :key="qq" class="as-chip pressable" @click="send(qq)">
            <span>{{ qq }}</span>
            <AppIcon name="chevron" :size="11" />
          </button>
        </div>
      </div>

      <div v-for="(m, i) in msgs" :key="i" class="as-row" :class="m.role">
        <AgentAvatar
          v-if="m.role === 'assistant'"
          :size="32"
          :state="m.streaming ? (m.content ? 'speaking' : 'thinking') : 'idle'"
          class="as-msg-avatar"
        />

        <div class="as-bubble" :class="{ me: m.role === 'user', 'is-thinking': m.role === 'assistant' && m.streaming && !m.content }">
          <!-- ============ AI 回复顶栏：青囊名号 + AI 生成标识 + 检索脉络胶囊 ============ -->
          <div v-if="m.role === 'assistant'" class="as-meta-bar">
            <span class="as-agent-name">青囊</span>
            <span class="as-tag">
              <AppIcon name="sparkles" :size="10" /> AI 生成
            </span>

            <!-- 思考等待期：实时秒表胶囊 -->
            <span v-if="m.streaming && !m.content" class="as-timer-pill">
              <span class="as-live-dot" />
              {{ formatSec(m.elapsedMs) }}
            </span>

            <!-- 开始输出后 / 已完成：可折叠的「库内检索脉络」胶囊 -->
            <button
              v-else-if="m.citations?.length || m.no_context"
              type="button"
              class="as-trace-pill pressable"
              @click="toggleTrace(m)"
            >
              <span v-if="m.streaming" class="as-live-dot" />
              <Check v-else :size="11" :stroke-width="2.6" class="as-done-check" />
              <span v-if="m.citations?.length">
                已检索 {{ m.citations.length }} 条库内依据
                <template v-if="m.ttftSec"> · {{ m.ttftSec }}s</template>
              </span>
              <span v-else>通用食养参考</span>
              <AppIcon name="chevron" :size="10" class="as-trace-arrow" :class="{ open: m.thinkOpen }" />
            </button>
          </div>

          <!-- 点击检索胶囊后展开的脉冲步骤回放 -->
          <Transition name="tk-fold">
            <div v-if="m.role === 'assistant' && m.thinkOpen && (m.content || !m.streaming)" class="as-trace-drawer">
              <div class="td-step">
                <Check :size="11" :stroke-width="2.6" class="td-dot" />
                <span>拆解提问意图并扫描药食同源知识库</span>
              </div>
              <div class="td-step">
                <Check :size="11" :stroke-width="2.6" class="td-dot" />
                <span v-if="m.citations?.length">
                  命中 {{ citeStats(m).summary }}（点击正文角标或下方卡片可溯源）
                </span>
                <span v-else>库内未命中直接同名条目，按日常食养通识提供温和参考</span>
              </div>
              <div v-if="m.usedConst" class="td-step">
                <Check :size="11" :stroke-width="2.6" class="td-dot" />
                <span>结合「{{ m.usedConst }}」体质倾向校准适宜配伍</span>
              </div>
            </div>
          </Transition>

          <!-- ============ 阶段一：首字到达前的灵动思考框 ============ -->
          <div v-if="m.role === 'assistant' && m.streaming && !m.content" class="as-think-box">
            <div class="tk-main">
              <!-- 呼吸本草罗盘动效球 -->
              <div class="tk-orb" aria-hidden="true">
                <span class="tk-ring tk-ring-1" />
                <span class="tk-ring tk-ring-2" />
                <span class="tk-orbit"><span class="tk-orbit-bead" /></span>
                <span class="tk-orb-core">
                  <AppIcon :name="thinkingState(m).icon" :size="16" :stroke-width="1.9" />
                </span>
              </div>

              <!-- 动态轮换工序标题 + 副文案 -->
              <div class="tk-copy">
                <Transition name="tk-swap" mode="out-in">
                  <div :key="thinkingState(m).key" class="tk-stage-text">
                    <div class="tk-headline-row">
                      <span class="tk-headline">{{ thinkingState(m).headline }}</span>
                      <span class="tk-wave-dots" aria-hidden="true"><i /><i /><i /></span>
                    </div>
                    <p class="tk-sub">{{ thinkingState(m).sub }}</p>
                  </div>
                </Transition>
              </div>
            </div>

            <!-- 三段式工序进度轨 -->
            <div class="tk-steps">
              <div class="tk-step" :class="{ done: thinkingState(m).stepIdx > 0, active: thinkingState(m).stepIdx === 0 }">
                <span class="tk-step-node">
                  <Check v-if="thinkingState(m).stepIdx > 0" :size="9" :stroke-width="3" />
                  <span v-else class="tk-bars"><i /><i /><i /></span>
                </span>
                <span class="tk-step-label">巡检知识库</span>
              </div>
              <span class="tk-step-line" :class="{ lit: thinkingState(m).stepIdx >= 1 }" />
              <div class="tk-step" :class="{ done: thinkingState(m).stepIdx > 1, active: thinkingState(m).stepIdx === 1 }">
                <span class="tk-step-node">
                  <Check v-if="thinkingState(m).stepIdx > 1" :size="9" :stroke-width="3" />
                  <span v-else-if="thinkingState(m).stepIdx === 1" class="tk-bars"><i /><i /><i /></span>
                  <span v-else class="tk-idle-dot" />
                </span>
                <span class="tk-step-label">
                  {{ m.citationsReady ? (m.citations?.length ? `锁定 ${m.citations.length} 条依据` : '整理参考范围') : '核验方药依据' }}
                </span>
              </div>
              <span class="tk-step-line" :class="{ lit: thinkingState(m).stepIdx >= 2 }" />
              <div class="tk-step" :class="{ active: thinkingState(m).stepIdx === 2 }">
                <span class="tk-step-node">
                  <span v-if="thinkingState(m).stepIdx === 2" class="tk-bars"><i /><i /><i /></span>
                  <span v-else class="tk-idle-dot" />
                </span>
                <span class="tk-step-label">生成食养解答</span>
              </div>
            </div>

            <!-- 实时命中的词条快闪标签（RAG 返回后瞬间弹出，不等首字） -->
            <Transition name="tk-fold">
              <div v-if="m.citations?.length" class="tk-hits">
                <span class="tk-hits-label">已调取：</span>
                <span
                  v-for="(c, ci) in m.citations.slice(0, 5)"
                  :key="c.id"
                  class="tk-hit-chip"
                  :style="{ '--delay': `${ci * 55}ms` }"
                >
                  <span class="tk-hit-id">{{ c.id }}</span>
                  <span>{{ c.title }}</span>
                </span>
              </div>
            </Transition>

            <!-- 底部竹青流光进度细线 -->
            <div class="tk-progress-bar" aria-hidden="true">
              <span class="tk-progress-runner" />
            </div>
          </div>

          <!-- ============ 阶段二：流式正文输出 / 历史消息内容 ============ -->
          <div v-else class="as-text" :class="{ typing: m.streaming }">
            <template v-for="(seg, si) in segments(m.content, m.citations)" :key="si">
              <button
                v-if="seg.cite"
                type="button"
                class="as-cite-ref pressable"
                :title="`查看引用：${seg.cite.title}`"
                @click="goCite(seg.cite)"
              >{{ seg.t }}</button>
              <b v-else-if="seg.b">{{ seg.t }}</b>
              <template v-else>{{ seg.t }}</template>
            </template>
            <span v-if="m.streaming" class="as-caret" aria-hidden="true" />
          </div>

          <div v-if="errTip && m.role === 'assistant' && i === msgs.length - 1" class="as-err">{{ errTip }}</div>

          <!-- 引用卡（方子/药材/成分），RAG 命中后立即浮现，可点击进详情 -->
          <div v-if="m.citations?.length" class="as-cites">
            <div class="as-cites-head">
              <span>参考依据（点击卡片查看详情）</span>
              <span class="as-cites-count">{{ citeStats(m).summary }}</span>
            </div>
            <button v-for="c in m.citations" :key="c.id" class="as-cite pressable" @click="goCite(c)">
              <span class="ac-cover">
                <img v-if="citeCover(c) && !citeImgFailed[c.id]"
                     :src="citeCover(c)" :alt="c.title" loading="lazy" @error="onCiteImgErr(c)" />
                <AppIcon v-else :name="citeIconName(c)" :size="18" />
              </span>
              <span class="ac-main">
                <span class="ac-top-line">
                  <span class="ac-id">{{ c.id }}</span>
                  <span class="ac-title">{{ c.title }}</span>
                </span>
                <span class="ac-sub">{{ c.sub }}<template v-if="formatCiteDetail(c)"> · {{ formatCiteDetail(c) }}</template></span>
              </span>
              <AppIcon name="chevron" :size="12" />
            </button>
          </div>
        </div>
      </div>

      <div v-if="sending" class="as-stop">
        <button class="as-stop-btn pressable" @click="stopStream">
          <span class="as-stop-sq" aria-hidden="true" />
          <span>停止生成</span>
        </button>
      </div>
    </div>

    <div class="as-input card">
      <textarea v-model="input" rows="1" placeholder="问问食养方子/药材/成分…（Enter 发送）"
                @keydown.enter.exact.prevent="send()" />
      <button class="as-send pressable" :disabled="sending || !input.trim()" @click="send()">
        <AppIcon name="chevron" :size="15" :stroke-width="2.4" />
      </button>
    </div>
    <DisclaimerBanner variant="ai" style="margin-top: 14px;" />
  </div>
</template>

<style scoped>
.as-page { max-width: 760px; margin: 0 auto; padding-bottom: 20px; }
.as-head { padding: 14px 16px; margin-bottom: 12px; }
.as-head-main { display: flex; align-items: center; gap: 12px; }
.as-head-copy { flex: 1; min-width: 0; }
.as-title { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; font-size: 16px; font-weight: 700; color: var(--ink-900); font-family: var(--font-serif); }
.as-persona-badge {
  font-family: var(--font-sans);
  font-size: 10.5px;
  font-weight: 600;
  color: var(--green-text);
  background: var(--green-50);
  border: 1px solid var(--green-100);
  padding: 1px 8px;
  border-radius: 999px;
  line-height: 17px;
}
.as-clear { margin-left: auto; border: none; background: none; color: var(--ink-400); font-size: 12px; cursor: pointer; font-family: inherit; transition: color var(--dur-fast) ease; }
.as-clear:hover { color: var(--cinnabar); }
.as-sub { font-size: 12px; color: var(--ink-400); margin: 4px 0 0; line-height: 1.55; }
.as-const { margin-top: 10px; padding-top: 9px; border-top: 1px dashed var(--card-border); }
.as-switch { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--ink-600); cursor: pointer; }
.as-switch input { accent-color: var(--green-600); }
.as-const-tip { margin: 4px 0 0 22px; font-size: 11px; color: var(--ink-400); }

.as-list { display: flex; flex-direction: column; gap: 14px; min-height: 40vh; }

/* 空态卡片 */
.as-empty { padding: 28px 20px; text-align: center; color: var(--ink-600); }
.as-empty-avatar {
  display: flex;
  justify-content: center;
  margin-bottom: 10px;
}
.as-empty-title { font-family: var(--font-serif); font-size: 16px; font-weight: 700; color: var(--ink-900); }
.as-empty-sub { font-size: 12.5px; color: var(--ink-400); max-width: 440px; margin: 6px auto 0; line-height: 1.65; }
.as-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 14px; }
.as-chip {
  display: inline-flex; align-items: center; gap: 5px;
  border: 1px solid var(--green-100); background: var(--green-50); color: var(--ink-600);
  font-size: 13px; font-family: inherit; padding: 6px 13px; border-radius: 999px; cursor: pointer;
  transition: border-color var(--dur-fast) ease, color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.as-chip svg { color: var(--ink-400); opacity: .7; transition: transform var(--dur-fast) ease; }
.as-chip:hover { border-color: var(--green-600); color: var(--green-text); }
.as-chip:hover svg { transform: translateX(2px); color: var(--green-600); opacity: 1; }

/* 消息行与青囊头像 */
.as-row { display: flex; gap: 10px; align-items: flex-start; }
.as-row.user { justify-content: flex-end; }
.as-msg-avatar { margin-top: 2px; }

/* 气泡主体：统一采用宣纸卡色 var(--card)，兼容暗黑模式 */
.as-bubble {
  max-width: min(84%, 620px);
  background: var(--card);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 11px 14px;
  font-size: 14px;
  line-height: 1.78;
  color: var(--ink-900);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--dur-med) ease, box-shadow var(--dur-med) ease;
}
.as-bubble.is-thinking {
  width: min(84%, 500px);
  border-color: rgba(58, 122, 94, 0.28);
  box-shadow: var(--shadow);
}
.as-bubble.me {
  background: var(--green-700);
  border-color: var(--green-700);
  color: #fdfaf1;
  border-bottom-right-radius: 5px;
  padding: 9px 14px;
}

/* 顶栏元数据：AI 生成标识 + 检索脉络胶囊 */
.as-meta-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 7px;
}
.as-agent-name {
  font-family: var(--font-serif);
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-900);
  letter-spacing: 0.02em;
}
.as-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10.5px;
  font-weight: 600;
  color: var(--green-text);
  background: var(--green-50);
  border: 1px solid var(--green-100);
  padding: 1px 7px;
  border-radius: 999px;
  line-height: 17px;
}
.as-timer-pill {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--ink-400);
  background: rgba(120, 95, 60, 0.06);
  padding: 1px 8px;
  border-radius: 999px;
  line-height: 17px;
}
.as-live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--green-600);
  animation: dotPing 1.3s ease-in-out infinite;
}
@keyframes dotPing {
  0%, 100% { transform: scale(0.85); opacity: 0.55; }
  50% { transform: scale(1.2); opacity: 1; }
}

.as-trace-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--card-border);
  background: rgba(120, 95, 60, 0.045);
  color: var(--ink-600);
  font-size: 11px;
  font-family: inherit;
  font-variant-numeric: tabular-nums;
  padding: 1px 8px;
  border-radius: 999px;
  line-height: 17px;
  cursor: pointer;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease, color var(--dur-fast) ease;
}
.as-trace-pill:hover {
  border-color: var(--green-600);
  color: var(--green-text);
  background: var(--green-50);
}
.as-done-check {
  color: var(--green-600);
  font-weight: 700;
  font-size: 10px;
}
.as-trace-arrow {
  color: var(--ink-400);
  transform: rotate(90deg);
  transition: transform var(--dur-fast) var(--ease-out-soft);
}
.as-trace-arrow.open {
  transform: rotate(-90deg);
}

/* 展开的检索步骤抽屉 */
.as-trace-drawer {
  margin: 0 0 9px;
  padding: 8px 10px;
  border-radius: 9px;
  background: rgba(58, 122, 94, 0.05);
  border: 1px dashed var(--green-100);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.td-step {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--ink-600);
}
.td-dot {
  flex-shrink: 0;
  color: var(--green-600);
  font-size: 10.5px;
  font-weight: 700;
}

/* ============ 灵动思考框（首字输出前） ============ */
.as-think-box {
  position: relative;
  border-radius: 11px;
  padding: 12px 12px 13px;
  background:
    radial-gradient(120% 100% at 0% 0%, rgba(58, 122, 94, 0.09) 0%, transparent 65%),
    rgba(120, 95, 60, 0.035);
  border: 1px solid rgba(58, 122, 94, 0.16);
  overflow: hidden;
}

.tk-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 本草罗盘呼吸球 */
.tk-orb {
  position: relative;
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.tk-orb-core {
  position: relative;
  z-index: 2;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--card);
  border: 1px solid var(--green-100);
  color: var(--green-700);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(42, 95, 74, 0.14);
  animation: tkFloat 2.4s ease-in-out infinite;
}
@keyframes tkFloat {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-1.5px) scale(1.04); }
}

.tk-ring {
  position: absolute;
  inset: 2px;
  border-radius: 50%;
  border: 1px solid rgba(58, 122, 94, 0.32);
  pointer-events: none;
  animation: tkRipple 2.4s cubic-bezier(0.22, 1, 0.36, 1) infinite;
}
.tk-ring-2 {
  animation-delay: 1.2s;
}
@keyframes tkRipple {
  0% { transform: scale(0.76); opacity: 0.75; }
  100% { transform: scale(1.22); opacity: 0; }
}

.tk-orbit {
  position: absolute;
  inset: 1px;
  border-radius: 50%;
  pointer-events: none;
  animation: tkOrbitSpin 3.2s linear infinite;
}
.tk-orbit-bead {
  position: absolute;
  top: -2px;
  left: 50%;
  width: 5px;
  height: 5px;
  margin-left: -2.5px;
  border-radius: 50%;
  background: var(--green-600);
  box-shadow: 0 0 6px rgba(58, 122, 94, 0.55);
}
@keyframes tkOrbitSpin {
  to { transform: rotate(360deg); }
}

/* 工序主副文案 + 柔光扫掠 */
.tk-copy {
  flex: 1;
  min-width: 0;
}
.tk-headline-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.tk-headline {
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.45;
  background: linear-gradient(90deg, var(--ink-900) 0%, var(--green-700) 45%, var(--amber-text) 65%, var(--ink-900) 100%);
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: tkShimmer 2.8s linear infinite;
}
@keyframes tkShimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -120% 0; }
}
.tk-sub {
  margin-top: 2px;
  font-size: 11.5px;
  line-height: 1.45;
  color: var(--ink-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 灵动三点跳波 */
.tk-wave-dots {
  display: inline-flex;
  align-items: center;
  gap: 2.5px;
  flex-shrink: 0;
  margin-left: 1px;
}
.tk-wave-dots i {
  width: 3.5px;
  height: 3.5px;
  border-radius: 50%;
  background: var(--green-600);
  animation: tkDotJump 1.2s ease-in-out infinite;
}
.tk-wave-dots i:nth-child(2) { animation-delay: 0.18s; }
.tk-wave-dots i:nth-child(3) { animation-delay: 0.36s; }
@keyframes tkDotJump {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.35; }
  40% { transform: translateY(-3px); opacity: 1; }
}

/* 工序切换纵向滑动过渡 */
.tk-swap-enter-active,
.tk-swap-leave-active {
  transition: opacity 0.22s ease, transform 0.22s var(--ease-out-soft);
}
.tk-swap-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.tk-swap-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* 三段式步骤轨 */
.tk-steps {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 11px;
  padding-top: 9px;
  border-top: 1px dashed rgba(120, 95, 60, 0.14);
}
.tk-step {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--ink-400);
  white-space: nowrap;
  transition: color var(--dur-fast) ease;
}
.tk-step.active {
  color: var(--green-text);
  font-weight: 600;
}
.tk-step.done {
  color: var(--ink-600);
}
.tk-step-node {
  width: 15px;
  height: 15px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 9.5px;
  font-weight: 700;
  background: rgba(120, 95, 60, 0.08);
  color: var(--ink-400);
}
.tk-step.done .tk-step-node {
  background: var(--green-100);
  color: var(--green-700);
}
.tk-step.active .tk-step-node {
  background: var(--green-50);
  border: 1px solid rgba(58, 122, 94, 0.35);
}
.tk-idle-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--ink-400);
  opacity: 0.45;
}
.tk-step-line {
  flex: 1;
  min-width: 10px;
  height: 1px;
  background: rgba(120, 95, 60, 0.16);
  transition: background var(--dur-med) ease;
}
.tk-step-line.lit {
  background: var(--green-600);
}

/* 迷你茶雾律动柱 */
.tk-bars {
  display: inline-flex;
  align-items: center;
  gap: 1.5px;
  height: 8px;
}
.tk-bars i {
  width: 1.8px;
  height: 7px;
  border-radius: 2px;
  background: var(--green-600);
  animation: tkBarPulse 0.9s ease-in-out infinite;
}
.tk-bars i:nth-child(1) { animation-delay: 0s; }
.tk-bars i:nth-child(2) { animation-delay: 0.2s; }
.tk-bars i:nth-child(3) { animation-delay: 0.4s; }
@keyframes tkBarPulse {
  0%, 100% { transform: scaleY(0.4); opacity: 0.55; }
  50% { transform: scaleY(1); opacity: 1; }
}

/* 实时调取的命中词条小胶囊 */
.tk-hits {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  margin-top: 9px;
}
.tk-hits-label {
  font-size: 11px;
  color: var(--ink-400);
}
.tk-hit-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--card);
  border: 1px solid var(--green-100);
  font-size: 11px;
  color: var(--ink-600);
  line-height: 16px;
  animation: tkChipIn 0.32s var(--ease-out-soft) backwards;
  animation-delay: var(--delay, 0ms);
}
.tk-hit-id {
  font-size: 9.5px;
  font-weight: 700;
  color: var(--green-text);
}
@keyframes tkChipIn {
  from { opacity: 0; transform: translateY(4px) scale(0.94); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* 底部竹青流光进度条 */
.tk-progress-bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2.5px;
  background: rgba(58, 122, 94, 0.10);
  overflow: hidden;
}
.tk-progress-runner {
  display: block;
  width: 42%;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, var(--green-600), var(--amber-600), transparent);
  animation: tkSweep 1.65s ease-in-out infinite;
}
@keyframes tkSweep {
  0% { transform: translateX(-110%); }
  100% { transform: translateX(340%); }
}

.tk-fold-enter-active,
.tk-fold-leave-active {
  transition: opacity 0.2s ease, transform 0.2s var(--ease-out-soft);
}
.tk-fold-enter-from,
.tk-fold-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ============ 正文与内联引用角标 ============ */
.as-text { white-space: pre-wrap; word-break: break-word; }
.as-cite-ref {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0 2px;
  padding: 0 5px;
  height: 17px;
  border-radius: 4px;
  border: 1px solid var(--green-100);
  background: var(--green-50);
  color: var(--green-text);
  font-size: 10.5px;
  font-weight: 700;
  font-family: var(--font-sans);
  line-height: 15px;
  vertical-align: 1px;
  cursor: pointer;
  transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease, color var(--dur-fast) ease;
}
.as-cite-ref:hover {
  background: var(--green-700);
  border-color: var(--green-700);
  color: #fdfaf1;
}

/* 温润呼吸光标胶囊 */
.as-caret {
  display: inline-block;
  width: 6px;
  height: 14px;
  margin-left: 3px;
  vertical-align: -2px;
  border-radius: 3px;
  background: var(--green-600);
  animation: caretBreath 0.9s ease-in-out infinite;
}
@keyframes caretBreath {
  0%, 100% { opacity: 1; transform: scaleY(1); }
  50% { opacity: 0.22; transform: scaleY(0.84); }
}

.as-err { margin-top: 6px; font-size: 12px; color: var(--cinnabar); }

/* ============ 引用卡片列表 ============ */
.as-cites {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 11px;
  border-top: 1px dashed var(--card-border);
  padding-top: 9px;
}
.as-cites-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--ink-400);
  margin-bottom: 1px;
}
.as-cites-count {
  color: var(--green-text);
  font-weight: 600;
}
.as-cite {
  display: flex; align-items: center; gap: 10px; text-align: left; width: 100%;
  border: 1px solid var(--card-border); background: rgba(120, 95, 60, 0.025); border-radius: 10px;
  padding: 8px 10px; cursor: pointer; font-family: inherit;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.as-cite:hover { border-color: var(--green-600); background: var(--green-50); }
.ac-cover {
  position: relative; width: 42px; height: 42px; border-radius: 8px; flex-shrink: 0;
  background: var(--green-50); border: 1px solid rgba(0,0,0,0.04);
  display: flex; align-items: center; justify-content: center;
  color: var(--tile-ink); overflow: hidden;
}
.ac-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ac-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.ac-top-line { display: flex; align-items: center; gap: 6px; min-width: 0; }
.ac-id {
  flex-shrink: 0;
  font-size: 10px; font-weight: 700; color: var(--green-text);
  background: var(--green-50); border: 1px solid var(--green-100);
  border-radius: 4px; padding: 0 5px; line-height: 15px;
}
.as-cite:hover .ac-id { background: var(--card); }
.ac-title { font-size: 13px; font-weight: 600; color: var(--ink-900); font-family: var(--font-serif); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ac-sub { font-size: 11px; color: var(--ink-400); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.as-cite svg { flex-shrink: 0; color: var(--ink-400); }

/* 停止生成胶囊按钮 */
.as-stop { display: flex; justify-content: center; margin-top: 2px; }
.as-stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--card-border);
  background: var(--card);
  color: var(--ink-600);
  font-size: 12px;
  font-family: inherit;
  padding: 6px 15px;
  border-radius: 999px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: color var(--dur-fast) ease, border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.as-stop-sq {
  width: 7px;
  height: 7px;
  border-radius: 2px;
  background: var(--cinnabar-soft);
}
.as-stop-btn:hover {
  color: var(--cinnabar);
  border-color: var(--cinnabar-soft);
  background: var(--red-50);
}

/* 底部输入栏 */
.as-input { display: flex; align-items: flex-end; gap: 8px; padding: 10px 12px; position: sticky; bottom: calc(12px + var(--tabbar-offset, 0px)); margin-top: 12px; z-index: 20; }
.as-input textarea {
  flex: 1; border: none; resize: none; outline: none; background: transparent;
  font-family: inherit; font-size: 14px; line-height: 1.5; color: var(--ink-900); max-height: 96px;
}
.as-send {
  flex-shrink: 0; width: 34px; height: 34px; border-radius: 50%; border: none; cursor: pointer;
  background: var(--green-700); color: #fdfaf1; display: inline-flex; align-items: center; justify-content: center;
}
.as-send:disabled { opacity: .4; cursor: not-allowed; }
.as-send svg { transform: rotate(-90deg); margin-top: -1px; }

/* 移动端窄屏步骤条自适应收紧 */
@media (max-width: 520px) {
  .as-bubble, .as-bubble.is-thinking { max-width: 89%; width: auto; }
  .tk-steps { gap: 4px; }
  .tk-step { font-size: 10.5px; }
}

/* 减弱动态效果无障碍兼容 */
@media (prefers-reduced-motion: reduce) {
  .as-avatar.thinking,
  .tk-orb-core,
  .tk-ring,
  .tk-orbit,
  .tk-headline,
  .tk-wave-dots i,
  .tk-bars i,
  .tk-progress-runner,
  .as-live-dot,
  .as-caret {
    animation: none !important;
  }
  .tk-headline {
    color: var(--ink-900);
    background: none;
  }
}
</style>
