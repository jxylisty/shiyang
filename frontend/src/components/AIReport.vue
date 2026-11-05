<script setup>
// AI 流式解读面板（P2 免门槛版）：
// - 默认无 Key 直接生成 → 后端回放平台预生成的解读（SSE 节奏）
// - 可选自带 DeepSeek/OpenAI Key → 实时个性化生成（Key 仅存本机浏览器，绝不提交后端存储）
import { ref, computed } from 'vue'
import { Sparkles } from '@lucide/vue'
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

// 轻量 Markdown 解析（纯组件渲染，不用 v-html 防注入）
// 支持：#/##/### 标题、**加粗**、*斜体*、空行分段、行内换行
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

function parseInline(str) {
  // 先按 ** 拆，再在每段里按 * 拆（避免 ** 被 * 吃掉）
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

const mdBlocks = computed(() => parseMarkdown(text.value))

function start() {
  phase.value = 'streaming'; text.value = ''; errMsg.value = ''
  const key = apiKey.value.trim()
  abort = streamAIReport(props.recipeId, key,
    (full, src) => { text.value = full; if (src) source.value = src },
    () => { phase.value = 'done' },
    (e) => { phase.value = 'error'; errMsg.value = typeof e === 'string' ? e : (e.message || 'AI 服务异常') })
}
function stop() { abort?.(); phase.value = 'idle'; text.value = '' }
function toggleKeyInput() { showKeyInput.value = !showKeyInput.value }
function saveKey() {
  localStorage.setItem(KEY_STORE, apiKey.value.trim())
  showKeyInput.value = false
}
</script>

<template>
  <div class="ai-panel">
    <template v-if="phase === 'idle'">
      <p class="ai-tip">让 AI 把这个方子的成分数据翻译成人话</p>
      <button class="btn ai-start-btn" @click="start"><Sparkles :size="15" :stroke-width="2.2" /> 生成 AI 解读</button>
      <div class="ai-key-row">
        <button class="ai-key-toggle" @click="toggleKeyInput">{{ showKeyInput ? '收起' : '用自己的 Key（可选）' }}</button>
        <!-- Key 输入行：高度过渡展开/收起；收起时按有无已存 Key 显示不同提示 -->
        <Transition name="key-grow">
          <div v-if="showKeyInput" class="key-wrap">
            <input v-model="apiKey" type="password" placeholder="sk-...（DeepSeek 或 OpenAI Key，仅存本机）" class="ai-key" @keyup.enter="saveKey" />
            <button class="btn ghost ai-key-save" @click="saveKey">保存</button>
          </div>
        </Transition>
        <p v-if="!showKeyInput && apiKey" class="ai-key-note">将使用你保存的 Key 实时生成 · <a href="javascript:void(0)" @click="showKeyInput = true">更换</a></p>
        <p v-if="!showKeyInput && !apiKey" class="ai-key-note">未填 Key 时展示平台预生成的通用解读</p>
      </div>
    </template>
    <template v-else>
      <Transition name="ai-fade" mode="out-in">
        <div class="ai-stream" key="stream">
          <div class="ai-md">
            <template v-for="(blk, bi) in mdBlocks" :key="bi">
              <h1 v-if="blk.type === 'h1'" class="md-h1">
                <template v-for="(s, si) in blk.spans" :key="si"><i v-if="s.i"><b v-if="s.b">{{ s.t }}</b><template v-else>{{ s.t }}</template></i><b v-else-if="s.b">{{ s.t }}</b><template v-else>{{ s.t }}</template></template>
              </h1>
              <h2 v-else-if="blk.type === 'h2'" class="md-h2">
                <template v-for="(s, si) in blk.spans" :key="si"><i v-if="s.i"><b v-if="s.b">{{ s.t }}</b><template v-else>{{ s.t }}</template></i><b v-else-if="s.b">{{ s.t }}</b><template v-else>{{ s.t }}</template></template>
              </h2>
              <h3 v-else-if="blk.type === 'h3'" class="md-h3">
                <template v-for="(s, si) in blk.spans" :key="si"><i v-if="s.i"><b v-if="s.b">{{ s.t }}</b><template v-else>{{ s.t }}</template></i><b v-else-if="s.b">{{ s.t }}</b><template v-else>{{ s.t }}</template></template>
              </h3>
              <p v-else class="md-p">
                <template v-for="(s, si) in blk.spans" :key="si"><i v-if="s.i"><b v-if="s.b">{{ s.t }}</b><template v-else>{{ s.t }}</template></i><b v-else-if="s.b">{{ s.t }}</b><template v-else>{{ s.t }}</template></template>
                <span v-if="phase === 'streaming' && bi === mdBlocks.length - 1" class="cursor">▍</span>
              </p>
            </template>
          </div>
          <p v-if="phase === 'streaming'" class="ai-status"><span class="ai-dots"></span>{{ source === 'pregen' ? 'AI 解读（预生成）加载中' : 'AI 正在解读' }}</p>
          <!-- AI 生成内容必须标注来源（AGENTS.md §2.6）：完成后常驻，不随流式状态消失 -->
          <p v-if="phase === 'done'" class="ai-src">
            <span class="ai-src-tag">AI 生成</span>{{ source === 'pregen' ? '平台预生成的通用解读' : '基于你的 Key 实时生成' }}，仅供参考
          </p>
          <p v-if="phase === 'error'" class="ai-err shake">{{ errMsg }}</p>
          <div class="ai-ops">
            <button v-if="phase !== 'streaming'" class="btn ghost" @click="phase = 'idle'">重新生成</button>
            <button v-if="phase === 'streaming'" class="btn ghost" @click="stop">停止</button>
          </div>
          <DisclaimerBanner variant="ai" style="margin-top: 12px;" />
        </div>
      </Transition>
    </template>
  </div>
</template>

<style scoped>
.ai-tip { font-size: 12.5px; color: var(--ink-600); margin-bottom: 10px; line-height: 1.55; }
.ai-start-btn { width: 100%; }
@media (min-width: 540px) {
  .ai-start-btn { width: auto; min-width: 176px; padding: 9px 22px; }
}
.ai-key-row { margin-top: 10px; }
.ai-key-toggle { border: none; background: none; color: var(--green-text); font-size: 12px; cursor: pointer; padding: 0; }
.key-wrap { overflow: hidden; }
.ai-key {
  width: 100%; padding: 10px 12px; border: 1px solid var(--green-100); border-radius: 10px;
  font-size: 13px; margin-top: 8px; outline: none; background: var(--card); color: var(--ink-900); box-sizing: border-box;
  transition: border-color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.ai-key:focus { border-color: var(--green-600); box-shadow: 0 0 0 3px rgba(53, 144, 104, 0.08); }
.ai-key-save { margin-top: 8px; font-size: 12px; padding: 7px 14px; }
.ai-key-note { font-size: 11px; color: var(--ink-400); margin-top: 6px; }
.ai-key-note a { color: var(--green-text); }
/* Key 行高度过渡 */
.key-grow-enter-active, .key-grow-leave-active { transition: opacity .25s ease, height .25s var(--ease-out-soft); }
.key-grow-enter-from, .key-grow-leave-to { opacity: 0; height: 0; }
/* idle → streaming 面板淡入 */
.ai-fade-enter-active, .ai-fade-leave-active { transition: opacity .25s ease, transform .25s var(--ease-out-soft); }
.ai-fade-enter-from, .ai-fade-leave-to { opacity: 0; transform: translateY(6px); }
.ai-stream { line-height: 1.8; }
.ai-md { font-size: 13.5px; color: var(--ink-900); }
.md-h1 { font-size: 17px; font-weight: 600; margin: 4px 0 12px; color: var(--ink-900); line-height: 1.4; }
.md-h2 { font-size: 15px; font-weight: 600; margin: 16px 0 8px; color: var(--ink-900); line-height: 1.5; }
.md-h3 { font-size: 14px; font-weight: 600; margin: 14px 0 6px; color: var(--ink-900); line-height: 1.5; }
.md-p { margin: 0 0 12px; }
.md-p:last-child { margin-bottom: 0; }
.ai-md b { font-weight: 600; color: var(--ink-900); }
.ai-md i { font-style: italic; }
.cursor { animation: blink 1s infinite; color: var(--green-600); margin-left: 1px; }
@keyframes blink { 50% { opacity: 0; } }
/* 生成中三点跳动 */
.ai-status { font-size: 12px; color: var(--green-600); margin-top: 8px; }
.ai-dots { display: inline-block; margin-right: 4px; }
.ai-dots::after {
  content: "…"; display: inline-block; overflow: hidden; vertical-align: bottom;
  animation: dots 1.4s steps(4) infinite; width: 0;
}
@keyframes dots { to { width: 1.2em; } }
.ai-err { font-size: 12.5px; color: var(--red-text); margin-top: 8px; }
/* 生成完成后的来源标注：小字灰调，不抢正文 */
.ai-src { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--ink-400); margin-top: 10px; }
.ai-src-tag { display: inline-block; padding: 1px 6px; border-radius: 4px; background: var(--green-50); border: 1px solid var(--green-100); color: var(--green-text); font-size: 10.5px; }
.ai-ops { margin-top: 10px; }
</style>
