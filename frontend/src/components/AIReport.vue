<script setup>
// AI 流式解读面板：Key 从 localStorage 读（用户在页面临时填写，绝不提交到后端存储）
import { ref } from 'vue'
import { streamAIReport } from '../api'

const props = defineProps({ recipeId: [String, Number] })
const emit = defineEmits(['need-login'])

const KEY_STORE = 'shiyang_ai_key'
const apiKey = ref(localStorage.getItem(KEY_STORE) || '')
const text = ref('')
const phase = ref('idle')   // idle | streaming | done | error
const errMsg = ref('')
let abort = null

function start() {
  if (!apiKey.value.trim()) { errMsg.value = '请先填写 AI API Key'; return }
  localStorage.setItem(KEY_STORE, apiKey.value.trim())
  phase.value = 'streaming'; text.value = ''; errMsg.value = ''
  abort = streamAIReport(props.recipeId, apiKey.value.trim(),
    (full) => { text.value = full },
    () => { phase.value = 'done' },
    (e) => { phase.value = 'error'; errMsg.value = typeof e === 'string' ? e : (e.message || 'AI 服务异常') })
}
function stop() { abort?.(); phase.value = 'idle'; text.value = '' }
</script>

<template>
  <div class="ai-panel">
    <template v-if="phase === 'idle'">
      <p class="ai-tip">让 AI 把这个方子的成分数据翻译成人话（需自备 DeepSeek/OpenAI API Key，Key 仅存本机浏览器）</p>
      <input v-model="apiKey" type="password" placeholder="sk-...（DeepSeek 或 OpenAI Key）" class="ai-key" @keyup.enter="start" />
      <button class="btn block" @click="start">生成 AI 解读</button>
    </template>
    <template v-else>
      <div class="ai-stream">
        <p class="ai-text">{{ text }}<span v-if="phase === 'streaming'" class="cursor">▍</span></p>
        <p v-if="phase === 'streaming'" class="ai-status">AI 正在解读…</p>
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
.ai-key {
  width: 100%; padding: 10px 12px; border: 1px solid #e5efe9; border-radius: 10px;
  font-size: 13px; margin-bottom: 10px; outline: none; background: #fff;
}
.ai-key:focus { border-color: #359068; }
.ai-stream { white-space: pre-wrap; }
.ai-text { font-size: 13.5px; line-height: 1.8; color: #1f2b26; }
.cursor { animation: blink 1s infinite; color: #2e7d5b; }
@keyframes blink { 50% { opacity: 0; } }
.ai-status { font-size: 12px; color: #359068; margin-top: 8px; }
.ai-err { font-size: 12.5px; color: #c25e50; margin-top: 8px; }
.ai-ops { margin-top: 10px; }
</style>
