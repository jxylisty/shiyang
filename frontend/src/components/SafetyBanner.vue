<script setup>
/**
 * 方子详情页安全提示条（T1-5）
 * 读取 localStorage 的人群模式（与方子库页共享 key），激活时向 /safety/check 查询
 * verdict=block 红条 / warn 黄条 / pass 不渲染。独立组件，不侵入 RecipeDetail 主流程。
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { ShieldAlert } from '@lucide/vue'
import { safetyCheck } from '../api'

const props = defineProps({ recipeId: { type: Number, required: true } })

const profile = ref(localStorage.getItem('shiyang_safety_profile') || '')
const result = ref(null)

// 跨页签同步人群模式（其他页面切换时此处联动）
function onStorage(e) {
  if (e.key === 'shiyang_safety_profile') profile.value = e.newValue || ''
}
onMounted(() => window.addEventListener('storage', onStorage))
onUnmounted(() => window.removeEventListener('storage', onStorage))

async function run() {
  result.value = null
  if (!profile.value || !props.recipeId) return
  try {
    result.value = (await safetyCheck(props.recipeId, profile.value)).data.data
  } catch { /* 静默：安全提示失败不阻塞详情页 */ }
}

watch(() => [props.recipeId, profile.value], run, { immediate: true })
</script>

<template>
  <div v-if="result?.verdict === 'block'" class="sf block">
    <ShieldAlert :size="14" />
    <div>
      <b>{{ result.profile_name }}人群不建议</b>
      <p v-for="b in result.blocks" :key="b.material">{{ b.material }}：{{ b.reason }}</p>
    </div>
  </div>
  <div v-else-if="result?.verdict === 'warn'" class="sf warn">
    <ShieldAlert :size="14" />
    <div>
      <b>{{ result.profile_name }}人群注意</b>
      <p v-for="w in result.warns" :key="w.material">{{ w.material }}：{{ w.reason }}</p>
    </div>
  </div>
</template>

<style scoped>
.sf { display: flex; gap: 8px; padding: 10px 12px; border-radius: 10px; font-size: 12px; line-height: 1.6; margin-bottom: 12px; }
.sf.block { background: var(--red-50); color: var(--red-text); }
.sf.warn { background: var(--amber-50); color: var(--amber-text); }
.sf b { font-size: 12px; }
.sf p { opacity: .9; }
</style>
