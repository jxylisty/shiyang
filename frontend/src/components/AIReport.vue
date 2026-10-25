<script setup>
// AI 流式解读面板（P2 免门槛版）：
// - 默认无 Key 直接生成 → 后端回放平台预生成的解读（SSE 节奏）
// - 可选自带 DeepSeek/OpenAI Key → 实时个性化生成（Key 仅存本机浏览器，绝不提交后端存储）
import { ref } from 'vue'
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
      <button class="btn block" @click="start">生成 AI 解读</button>
      <div class="ai-key-row">
        <button class="ai-key-toggle" @click="toggleKeyInput">{{ showKeyInput ? '收起' : '用自己的 Key（可选）' }}</button>
        <template v-if="showKeyInput">
          <input v-model="apiKey" type="password" placeholder="sk-...（DeepSeek 或 OpenAI Key，仅存本机）" class="ai-key" @keyup.enter="saveKey" />
          <button class="btn ghost ai-key-save" @click="saveKey">保存</button>
        </template>
        <p v-else-if="apiKey" class="ai-key-note">将使用你保存的 Key 实时生成 · <a href="javascript:void(0)" @click="showKeyInput = true">更换</a></p>
        <p v-else class="ai-key-note">未填 Key 时展示平台预生成的通用解读</p>
      </div>
    </template>
    <template v-else>
      <div class="ai-stream">
        <p class="ai-text">{{ text }}<span v-if="phase === 'streaming'" class="cursor">▍</span></p>
        <p v-if="phase === 'streaming'" class="ai-status">{{ source === 'pregen' ? 'AI 解读（预生成）加载中…' : 'AI 正在解读…' }}</p>
        <p v-if="phase === 'error'" class="ai-err">{{ errMsg }}</p>
        <div class="ai-ops">
          <button v-if="phase !== 'streaming'" class="btn ghost" @click="phase = 'idle'">重新生成</button>
          <button v-if="phase === 'streaming'" class="btn ghost" @click="stop">停止</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ai-tip { font-size: 12px; color: #8a978f; margin-bottom: 8px; line-height: 1.5; }
.ai-key-row { margin-top: 10px; }
.ai-key-toggle { border: none; background: none; color: var(--green-700); font-size: 12px; cursor: pointer; padding: 0; }
.ai-key {
  width: 100%; padding: 10px 12px; border: 1px solid #e5efe9; border-radius: 10px;
  font-size: 13px; margin-top: 8px; outline: none; background: #fff; box-sizing: border-box;
}
.ai-key:focus { border-color: #359068; }
.ai-key-save { margin-top: 8px; font-size: 12px; padding: 7px 14px; }
.ai-key-note { font-size: 11px; color: #8a978f; margin-top: 6px; }
.ai-key-note a { color: var(--green-700); }
.ai-stream { white-space: pre-wrap; }
.ai-text { font-size: 13.5px; line-height: 1.8; color: #1f2b26; }
.cursor { animation: blink 1s infinite; color: #2e7d5b; }
@keyframes blink { 50% { opacity: 0; } }
.ai-status { font-size: 12px; color: #359068; margin-top: 8px; }
.ai-err { font-size: 12.5px; color: #c25e50; margin-top: 8px; }
.ai-ops { margin-top: 10px; }
</style>
