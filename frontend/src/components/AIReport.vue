<script setup>
// AI 功效深度解读面板（食养 Agent 版）：
// - 默认无 Key → 自动流畅回放平台预生成的深度功效解读
// - 可选自带 Key → 实时个性化调用模型生成
// - 结构化分块展示：【核心功效】【配伍奥秘】【通俗机理】【冲泡建议与避坑】
import { ref, computed, onMounted } from 'vue'
import { Sparkles, RotateCcw, SlidersHorizontal, AlertCircle, Target, Leaf, Lightbulb, Coffee } from '@lucide/vue'
import AgentAvatar from './AgentAvatar.vue'
import DisclaimerBanner from './DisclaimerBanner.vue'
import { streamAIReport } from '../api'

const props = defineProps({ recipeId: [String, Number] })

const KEY_STORE = 'shiyang_ai_key'
const showKeyInput = ref(false)
const apiKey = ref(localStorage.getItem(KEY_STORE) || '')
const text = ref('')
const phase = ref('idle')   // idle | streaming | done | error
const errMsg = ref('')
const source = ref('')      // pregen | live
let abort = null

// ---- 智能分节映射（专业线性 SVG 图标，杜绝 Emoji） ----
const SECTION_META = [
  { match: /核心功效|主打场景/, title: '核心功效与主打场景', icon: Target, badge: '核心主攻', cls: 'sec-efficacy' },
  { match: /配伍组合|奥秘/, title: '配伍组合的奥秘', icon: Leaf, badge: '配方协同', cls: 'sec-synergy' },
  { match: /感觉舒服|通俗机理|机理/, title: '为什么感觉舒服（通俗机理）', icon: Lightbulb, badge: '食养机理', cls: 'sec-mechanism' },
  { match: /冲泡建议|避坑提醒|注意事项|禁忌/, title: '冲泡建议与避坑提醒', icon: Coffee, badge: '实用指南', cls: 'sec-tips' },
]

function parseInline(str) {
  const parts = []
  const boldChunks = str.split('**')
  const oddBold = (boldChunks.length - 1) % 2 === 1
  boldChunks.forEach((chunk, bi) => {
    const isBold = bi % 2 === 1 && !(oddBold && bi === boldChunks.length - 1)
    const italicChunks = chunk.split('*')
    const oddItalic = (italicChunks.length - 1) % 2 === 1
    italicChunks.forEach((seg, si) => {
      if (!seg) return
      const isItalic = si % 2 === 1 && !(oddItalic && si === italicChunks.length - 1)
      parts.push({ t: seg, b: isBold, i: isItalic })
    })
  })
  return parts
}

// 结构化分块计算属性
const structuredSections = computed(() => {
  const raw = String(text.value || '').trim()
  if (!raw || (!raw.includes('【') && !raw.includes('['))) return []

  const lines = raw.split('\n')
  const sections = []
  let curr = null

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const m = trimmed.match(/^[【\[](.+?)[】\]]/)
    if (m) {
      if (curr) sections.push(curr)
      const rawTitle = m[1].trim()
      const meta = SECTION_META.find(s => s.match.test(rawTitle)) || {
        title: rawTitle, icon: Sparkles, badge: '重点解读', cls: 'sec-custom'
      }
      const rest = trimmed.slice(m[0].length).trim()
      curr = {
        title: meta.title,
        icon: meta.icon,
        badge: meta.badge,
        cls: meta.cls,
        paras: rest ? [parseInline(rest)] : []
      }
    } else {
      if (curr) {
        curr.paras.push(parseInline(trimmed))
      } else {
        curr = {
          title: '食养概述',
          icon: Sparkles,
          badge: '导读',
          cls: 'sec-custom',
          paras: [parseInline(trimmed)]
        }
      }
    }
  }
  if (curr) sections.push(curr)
  return sections
})

// 回退用轻量 Markdown 解析
function parseMarkdown(md) {
  const lines = String(md || '').replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let paraBuf = []

  function flushPara() {
    if (!paraBuf.length) return
    blocks.push({ type: 'p', spans: parseInline(paraBuf.join(' ')) })
    paraBuf = []
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (!line.trim()) { flushPara(); continue }
    let m
    if ((m = line.match(/^(#{1,3})\s+(.*)/))) {
      flushPara()
      blocks.push({ type: 'h' + m[1].length, spans: parseInline(m[2].trim()) })
    } else {
      paraBuf.push(line)
    }
  }
  flushPara()
  return blocks
}

const fallbackBlocks = computed(() => parseMarkdown(text.value))

function start() {
  phase.value = 'streaming'; text.value = ''; errMsg.value = ''
  const key = apiKey.value.trim()
  abort = streamAIReport(props.recipeId, key,
    (full, src) => { text.value = full; if (src) source.value = src },
    () => { phase.value = 'done' },
    (e) => { phase.value = 'error'; errMsg.value = typeof e === 'string' ? e : (e.message || 'AI 服务异常') })
}

function stop() { abort?.(); phase.value = 'done' }
function toggleKeyInput() { showKeyInput.value = !showKeyInput.value }
function saveKey() {
  localStorage.setItem(KEY_STORE, apiKey.value.trim())
  showKeyInput.value = false
  start()
}

onMounted(() => {
  if (props.recipeId) {
    start()
  }
})
</script>

<template>
  <div class="ai-panel">
    <!-- 头部操作条：标题 + Agent标识 + 重新生成操作 -->
    <div class="ai-head-bar">
      <div class="ai-title-wrap">
        <AgentAvatar :size="26" :state="phase === 'streaming' ? (text ? 'speaking' : 'thinking') : 'idle'" />
        <span class="ai-title">食养核心功效解读</span>
        <span class="agent-tag">青囊 · 寻证助手</span>
      </div>
      <div class="ai-head-ops">
        <button v-if="phase === 'done' || phase === 'error'" class="btn-regen" @click="start" title="重新生成解读">
          <RotateCcw :size="12" :stroke-width="2.2" /> 重新生成
        </button>
        <button v-else-if="phase === 'streaming'" class="btn-stop" @click="stop">
          停止
        </button>
      </div>
    </div>

    <!-- 自定义 Key 折叠切换 -->
    <div class="ai-key-bar">
      <button class="ai-key-toggle" @click="toggleKeyInput">
        <SlidersHorizontal :size="11" />
        {{ showKeyInput ? '收起配置' : (apiKey ? '已配置自定义 Key' : '自定义 Key 生成（可选）') }}
      </button>
      <Transition name="key-grow">
        <div v-if="showKeyInput" class="key-wrap">
          <div class="key-input-box">
            <input v-model="apiKey" type="password" placeholder="sk-...（支持 DeepSeek / OpenAI，仅存本机）" class="ai-key" @keyup.enter="saveKey" />
            <button class="btn ghost ai-key-save" @click="saveKey">保存生效</button>
          </div>
          <p class="ai-key-hint">未填写 Key 时，系统将自动回放平台专家模型预生成的深度解读。</p>
        </div>
      </Transition>
    </div>

    <!-- 异常状态 -->
    <div v-if="phase === 'error'" class="ai-err-box">
      <AlertCircle :size="14" />
      <span>{{ errMsg }}</span>
      <button class="btn-err-retry" @click="start">重试</button>
    </div>

    <!-- 正文展示：优先结构化卡片，回退普通 Markdown -->
    <div class="ai-content-wrap">
      <template v-if="structuredSections.length">
        <div v-for="(sec, sidx) in structuredSections" :key="sec.title + sidx"
             class="ai-sec-card" :class="sec.cls">
          <div class="sec-head">
            <span class="sec-icon-wrap">
              <component :is="sec.icon" :size="13" :stroke-width="2.3" class="sec-icon-svg" />
            </span>
            <span class="sec-title">{{ sec.title }}</span>
            <span class="sec-badge">{{ sec.badge }}</span>
          </div>
          <div class="sec-body">
            <p v-for="(para, pidx) in sec.paras" :key="pidx" class="sec-p">
              <template v-for="(s, sidx2) in para" :key="sidx2">
                <b v-if="s.b">{{ s.t }}</b>
                <i v-else-if="s.i">{{ s.t }}</i>
                <template v-else>{{ s.t }}</template>
              </template>
              <span v-if="phase === 'streaming' && sidx === structuredSections.length - 1 && pidx === sec.paras.length - 1" class="cursor">▍</span>
            </p>
          </div>
        </div>
      </template>

      <!-- 普通 Markdown 回退（或初始几字尚未出现【】时） -->
      <template v-else-if="text">
        <div class="ai-fallback-box">
          <div class="ai-md">
            <template v-for="(blk, bi) in fallbackBlocks" :key="bi">
              <p class="md-p">
                <template v-for="(s, si) in blk.spans" :key="si">
                  <b v-if="s.b">{{ s.t }}</b>
                  <i v-else-if="s.i">{{ s.t }}</i>
                  <template v-else>{{ s.t }}</template>
                </template>
                <span v-if="phase === 'streaming' && bi === fallbackBlocks.length - 1" class="cursor">▍</span>
              </p>
            </template>
          </div>
        </div>
      </template>

      <!-- 正在载入中动效（无文字阶段） -->
      <div v-if="phase === 'streaming' && !text" class="ai-loading-box">
        <div class="skl" style="height: 20px; width: 60%; margin-bottom: 8px;"></div>
        <div class="skl" style="height: 14px; width: 90%; margin-bottom: 6px;"></div>
        <div class="skl" style="height: 14px; width: 80%;"></div>
        <p class="ai-loading-tip"><AgentAvatar :size="22" state="thinking" /><span class="ai-dots"></span>青囊正在拆解方剂配伍与成分依据…</p>
      </div>
    </div>

    <!-- 底部来源说明与合规声明 -->
    <div class="ai-footer">
      <p class="ai-src">
        <span class="ai-src-tag">AI 生成</span>
        {{ source === 'pregen' ? '平台专家模型预生成的深度解读' : '基于自定义 Key 实时生成' }}，仅供食养调理参考
      </p>
      <DisclaimerBanner variant="ai" style="margin-top: 8px;" />
    </div>
  </div>
</template>

<style scoped>
.ai-panel {
  display: flex;
  flex-direction: column;
}

/* 顶部操作条 */
.ai-head-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--green-50);
  margin-bottom: 8px;
}
.ai-title-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ai-title-icon {
  color: var(--green-700);
}
.ai-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-900);
}
.agent-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--green-100);
  color: var(--green-text);
  font-weight: 600;
  letter-spacing: 0.02em;
}
.btn-regen {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: var(--green-text);
  background: var(--green-50);
  border: 1px solid var(--green-100);
  border-radius: 12px;
  padding: 3px 9px;
  cursor: pointer;
  transition: all var(--dur-fast) ease;
}
.btn-regen:hover {
  background: var(--green-100);
}
.btn-stop {
  font-size: 11.5px;
  color: var(--red-text);
  background: var(--red-50);
  border: 1px solid rgba(225, 29, 72, 0.2);
  border-radius: 12px;
  padding: 3px 9px;
  cursor: pointer;
}

/* 自定义 Key 配置条 */
.ai-key-bar {
  margin-bottom: 10px;
}
.ai-key-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: none;
  color: var(--ink-400);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 0;
  transition: color var(--dur-fast) ease;
}
.ai-key-toggle:hover {
  color: var(--green-text);
}
.key-wrap {
  margin-top: 6px;
  padding: 8px 10px;
  background: var(--green-50);
  border-radius: 8px;
}
.key-input-box {
  display: flex;
  gap: 6px;
}
.ai-key {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--green-100);
  border-radius: 6px;
  font-size: 12px;
  background: var(--card);
  color: var(--ink-900);
}
.ai-key:focus {
  border-color: var(--green-600);
  outline: none;
}
.ai-key-save {
  padding: 4px 10px;
  font-size: 11.5px;
}
.ai-key-hint {
  font-size: 10.5px;
  color: var(--ink-400);
  margin-top: 4px;
}
.key-grow-enter-active, .key-grow-leave-active {
  transition: opacity .2s ease, height .2s var(--ease-out-soft);
}
.key-grow-enter-from, .key-grow-leave-to {
  opacity: 0;
  height: 0;
}

/* 异常提示 */
.ai-err-box {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--red-50);
  color: var(--red-text);
  border-radius: 8px;
  font-size: 12px;
  margin-bottom: 10px;
}
.btn-err-retry {
  margin-left: auto;
  border: none;
  background: none;
  color: var(--red-text);
  font-weight: 700;
  cursor: pointer;
}

/* 结构化分块卡片样式 */
.ai-content-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai-sec-card {
  border-radius: 10px;
  padding: 10px 12px;
  border: 1px solid transparent;
  transition: transform var(--dur-fast) ease;
}
.sec-head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 7px;
}
.sec-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  flex-shrink: 0;
}
.sec-icon-svg {
  display: block;
}
.sec-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-900);
}
.sec-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: auto;
}
.sec-body {
  font-size: 13px;
  line-height: 1.65;
  color: var(--ink-800);
}
.sec-p {
  margin: 0 0 6px;
}
.sec-p:last-child {
  margin-bottom: 0;
}
.sec-p b {
  font-weight: 700;
  color: var(--ink-900);
}

/* 分块主题配色 */
.sec-efficacy {
  background: rgba(53, 144, 104, 0.06);
  border-color: rgba(53, 144, 104, 0.16);
}
.sec-efficacy .sec-icon-wrap {
  background: rgba(53, 144, 104, 0.14);
  color: var(--green-700);
}
.sec-efficacy .sec-badge {
  background: var(--green-100);
  color: var(--green-text);
}
.sec-efficacy .sec-p b {
  color: var(--green-800);
}

.sec-synergy {
  background: rgba(16, 149, 193, 0.05);
  border-color: rgba(16, 149, 193, 0.16);
}
.sec-synergy .sec-icon-wrap {
  background: rgba(16, 149, 193, 0.14);
  color: #0b7285;
}
.sec-synergy .sec-badge {
  background: rgba(16, 149, 193, 0.12);
  color: #0b7285;
}

.sec-mechanism {
  background: rgba(217, 119, 6, 0.05);
  border-color: rgba(217, 119, 6, 0.16);
}
.sec-mechanism .sec-icon-wrap {
  background: rgba(217, 119, 6, 0.14);
  color: var(--amber-700);
}
.sec-mechanism .sec-badge {
  background: rgba(217, 119, 6, 0.12);
  color: var(--amber-text);
}

.sec-tips {
  background: rgba(225, 29, 72, 0.04);
  border-color: rgba(225, 29, 72, 0.16);
}
.sec-tips .sec-icon-wrap {
  background: rgba(225, 29, 72, 0.12);
  color: var(--red-text);
}
.sec-tips .sec-badge {
  background: rgba(225, 29, 72, 0.1);
  color: var(--red-text);
}

.sec-custom {
  background: var(--green-50);
  border-color: var(--green-100);
}
.sec-custom .sec-icon-wrap {
  background: var(--green-100);
  color: var(--green-700);
}
.sec-custom .sec-badge {
  background: var(--green-100);
  color: var(--green-text);
}

/* 回退普通样式 */
.ai-fallback-box {
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-800);
}
.md-p {
  margin-bottom: 8px;
}
.md-p:last-child {
  margin-bottom: 0;
}
.md-p b {
  font-weight: 700;
  color: var(--green-800);
}

/* 加载动画 */
.ai-loading-box {
  padding: 12px 0;
}
.ai-loading-tip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--green-text);
  margin-top: 10px;
}
.ai-dots::after {
  content: "…";
  display: inline-block;
  overflow: hidden;
  vertical-align: bottom;
  animation: dots 1.4s steps(4) infinite;
  width: 0;
}
@keyframes dots {
  to { width: 1.2em; }
}

.cursor {
  animation: blink 1s infinite;
  color: var(--green-600);
  margin-left: 2px;
}
@keyframes blink {
  50% { opacity: 0; }
}

/* 底部标注 */
.ai-footer {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--green-50);
}
.ai-src {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--ink-400);
}
.ai-src-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--green-50);
  border: 1px solid var(--green-100);
  color: var(--green-text);
  font-size: 10px;
}
</style>
