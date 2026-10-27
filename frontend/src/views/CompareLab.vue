<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FlaskConical, ArrowLeftRight, AlertTriangle } from '@lucide/vue'
import { listRecipes, compareRecipes } from '../api'

const route = useRoute()
const router = useRouter()
const all = ref([])            // 全部方子（选择器数据源）
const aId = ref(Number(route.query.a) || null)
const bId = ref(Number(route.query.b) || null)
const result = ref(null)
const loading = ref(false)
const error = ref('')

const showPicker = ref(null)   // 'a' | 'b' | null：底部弹出选择器
// van-popup 的 show 是布尔；这里用 computed 桥接「哪个槽位在选」
const pickerShow = computed({
  get: () => showPicker.value != null,
  set: (v) => { if (!v) showPicker.value = null },
})

// 宽屏居中弹窗，窄屏底部抽屉（同口径）
const mqWide = window.matchMedia('(min-width: 720px)')
const isWide = ref(mqWide.matches)
const onMq = (e) => { isWide.value = e.matches }
onMounted(() => mqWide.addEventListener('change', onMq))
onUnmounted(() => mqWide.removeEventListener('change', onMq))

function pick(id) {
  if (showPicker.value === 'a') aId.value = id
  else bId.value = id
  showPicker.value = null
  if (ready.value) runCompare()
}

onMounted(async () => {
  try {
    all.value = (await listRecipes({ size: 100 })).data.data.items
  } catch { error.value = '方子列表加载失败' }
  if (aId.value && bId.value) runCompare()
})

async function runCompare() {
  if (!aId.value || !bId.value || aId.value === bId.value) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = (await compareRecipes(aId.value, bId.value)).data.data
    router.replace({ query: { a: aId.value, b: bId.value } })
  } catch (e) {
    error.value = e?.response?.status === 404 ? '所选方子暂无成分分析' : '对比加载失败'
  } finally { loading.value = false }
}

const aName = computed(() => all.value.find(r => r.id === aId.value)?.name || '选择方子 A')
const bName = computed(() => all.value.find(r => r.id === bId.value)?.name || '选择方子 B')
const ready = computed(() => aId.value && bId.value && aId.value !== bId.value)

const pct = (j) => Math.round(j * 100)
const radarNames = ['抗炎', '免疫调节', '气道修复']
const radarMax = computed(() => {
  const vals = [...(result.value?.radar.a || []), ...(result.value?.radar.b || [])].filter(v => v != null)
  return Math.max(100, ...vals)
})
// 雷达维度的 polygon 点位（中心 60,60 半径 52）
function poly(vals) {
  const n = radarNames.length
  return vals.map((v, i) => {
    const r = ((v ?? 0) / radarMax.value) * 52
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / n
    return `${(60 + r * Math.cos(ang)).toFixed(1)},${(60 + r * Math.sin(ang)).toFixed(1)}`
  }).join(' ')
}
</script>

<template>
  <div class="page">
    <div class="card head-card">
      <h2 class="lab-title"><FlaskConical :size="18" /> 对比实验室</h2>
      <p class="lab-sub">两个方子并排比：成分覆盖、入血化合物重叠、靶点与通路差异</p>
      <div class="pick-row">
        <button class="pick" :class="{ done: aId }" @click="showPicker = 'a'">{{ aName }}</button>
        <span class="vs"><ArrowLeftRight :size="16" /></span>
        <button class="pick" :class="{ done: bId }" @click="showPicker = 'b'">{{ bName }}</button>
      </div>
      <button class="btn lab-btn" :disabled="!ready || loading" @click="runCompare">
        {{ loading ? '分析中…' : '开始对比' }}
      </button>
    </div>

    <van-empty v-if="error" image="error" :description="error" />

    <template v-if="result">
      <!-- 头部对照 -->
      <div class="card vs-card">
        <div class="vs-grid">
          <router-link class="vs-side" :to="`/recipes/${result.a.id}`">
            <b>{{ result.a.name }}</b>
            <span class="vs-type">{{ result.a.type }} · {{ result.a.materials.length }} 味配料</span>
            <p class="vs-one">{{ result.a.oneliner }}</p>
          </router-link>
          <router-link class="vs-side" :to="`/recipes/${result.b.id}`">
            <b>{{ result.b.name }}</b>
            <span class="vs-type">{{ result.b.type }} · {{ result.b.materials.length }} 味配料</span>
            <p class="vs-one">{{ result.b.oneliner }}</p>
          </router-link>
        </div>
      </div>

      <!-- 成分重叠 -->
      <div class="section-title">成分重叠</div>
      <div class="card">
        <div class="j-line">
          <span>成分重叠度 <b class="j-num">{{ pct(result.compound.jaccard) }}%</b></span>
          <span class="tag">{{ result.compound.overlap_label }}</span>
        </div>
        <div class="duo">
          <div class="duo-col">
            <h4>高入血成分（≥70%）</h4>
            <p class="duo-n">{{ result.compound.hi_blood_a.length }} 个 · A</p>
            <p class="duo-n">{{ result.compound.hi_blood_b.length }} 个 · B</p>
            <p class="duo-share" v-if="result.compound.hi_blood_shared.length">
              共同 {{ result.compound.hi_blood_shared.length }} 个：{{ result.compound.hi_blood_shared.slice(0, 6).join('、') }}<span v-if="result.compound.hi_blood_shared.length > 6"> 等</span>
            </p>
            <p class="duo-share dim" v-else>无共同高入血成分——两者作用方向可能不同</p>
          </div>
        </div>
        <div class="duo" v-if="result.compound.shared.length">
          <div class="duo-col">
            <h4>共同活性成分（{{ result.compound.shared.length }}）</h4>
            <div class="chip-wrap">
              <span v-for="n in result.compound.shared" :key="n" class="tag">{{ n }}</span>
            </div>
          </div>
        </div>
        <div class="duo">
          <div class="duo-col">
            <h4>仅 A 有（{{ result.compound.only_a.length }}）</h4>
            <div class="chip-wrap"><span v-for="n in result.compound.only_a.slice(0, 10)" :key="n" class="tag dim-tag">{{ n }}</span></div>
          </div>
          <div class="duo-col">
            <h4>仅 B 有（{{ result.compound.only_b.length }}）</h4>
            <div class="chip-wrap"><span v-for="n in result.compound.only_b.slice(0, 10)" :key="n" class="tag dim-tag">{{ n }}</span></div>
          </div>
        </div>
      </div>

      <!-- 靶点 -->
      <div class="section-title">作用靶点</div>
      <div class="card">
        <div class="j-line">
          <span>靶点重叠度 <b class="j-num">{{ pct(result.target.jaccard) }}%</b></span>
          <span class="tag">{{ result.target.overlap_label }}</span>
        </div>
        <p class="hint">A 覆盖 {{ result.target.only_a.length + result.target.shared.length }} 个靶点，B 覆盖 {{ result.target.only_b.length + result.target.shared.length }} 个</p>
        <div v-if="result.target.shared.length" class="chip-wrap">
          <span v-for="g in result.target.shared" :key="g" class="tag gene">{{ g }}</span>
        </div>
        <p v-else class="hint">两者热门靶点没有交集，作用通路差异明显</p>
      </div>

      <!-- 三维机制雷达 -->
      <div class="section-title">机制强度对照</div>
      <div class="card radar-card">
        <svg viewBox="0 0 120 120" class="radar">
          <polygon points="60,8 112,60 60,112 8,60" fill="none" stroke="var(--green-100)" />
          <polygon points="60,34 86,60 60,86 34,60" fill="none" stroke="var(--green-100)" />
          <polygon :points="poly(result.radar.a)" fill="rgba(53,144,104,.18)" stroke="var(--green-600)" stroke-width="1.5" />
          <polygon :points="poly(result.radar.b)" fill="rgba(201,138,45,.15)" stroke="var(--amber-600)" stroke-width="1.5" stroke-dasharray="4 2" />
        </svg>
        <div class="radar-side">
          <div class="legend"><i class="dot a" />{{ result.a.name }}</div>
          <div class="legend"><i class="dot b" />{{ result.b.name }}</div>
          <div class="radar-rows">
            <div v-for="(name, i) in radarNames" :key="name" class="radar-row">
              <span>{{ name }}</span>
              <b>{{ result.radar.a[i]?.toFixed(0) ?? '—' }}</b>
              <span class="sep">vs</span>
              <b class="amber">{{ result.radar.b[i]?.toFixed(0) ?? '—' }}</b>
            </div>
          </div>
        </div>
      </div>

      <!-- 体质适宜 -->
      <div class="section-title">体质适宜对照</div>
      <div class="card">
        <div class="duo">
          <div class="duo-col">
            <h4>{{ result.a.name }} 适合</h4>
            <div class="chip-wrap"><span v-for="c in result.a.constitutions_suitable" :key="c" class="tag">{{ c }}</span></div>
          </div>
          <div class="duo-col">
            <h4>{{ result.b.name }} 适合</h4>
            <div class="chip-wrap"><span v-for="c in result.b.constitutions_suitable" :key="c" class="tag">{{ c }}</span></div>
          </div>
        </div>
        <p v-if="result.constitution.both_suitable.length" class="hint ok">
          两者都适合：{{ result.constitution.both_suitable.join('、') }} 体质，可按场景口味任选
        </p>
        <p v-if="result.constitution.warn_a.length || result.constitution.warn_b.length" class="hint warn">
          <AlertTriangle :size="13" style="vertical-align: -2px" />
          注意：{{ result.constitution.warn_a.length ? `${result.a.name} 不宜 ${result.constitution.warn_a.join('、')}体质` : '' }}
          {{ result.constitution.warn_b.length ? `${result.b.name} 不宜 ${result.constitution.warn_b.join('、')}体质` : '' }}
        </p>
      </div>
    </template>

    <!-- 选择器抽屉 -->
    <van-popup :show="pickerShow" @update:show="pickerShow = $event" :position="isWide ? 'center' : 'bottom'" round :class="{ 'wide-popup': isWide }" :style="{ maxHeight: '70%' }">
      <div class="picker">
        <h3>选择方子 {{ showPicker === 'a' ? 'A' : 'B' }}</h3>
        <div class="picker-list">
          <button v-for="r in all" :key="r.id" class="picker-item"
                  :class="{ active: (showPicker === 'a' ? aId : bId) === r.id }"
                  @click="pick(r.id)">
            <span class="pi-name">{{ r.name }}</span>
            <span class="pi-sub">{{ r.type }} · {{ r.scenes[0] || '' }}</span>
          </button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.head-card { text-align: center; padding: 20px 16px; }
.lab-title { font-family: var(--font-serif); font-size: 19px; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 6px; color: var(--green-text); }
.lab-sub { font-size: 12px; color: var(--ink-400); margin: 6px 0 14px; }
.pick-row { display: flex; align-items: center; gap: 8px; }
.pick {
  flex: 1; min-width: 0; padding: 10px 8px; border-radius: 12px; border: 1.5px dashed var(--green-100);
  background: var(--green-50); font-size: 14px; font-weight: 600; color: var(--ink-600);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer;
}
.pick.done { border-style: solid; border-color: var(--green-600); background: var(--card); color: var(--ink-900); }
.vs { color: var(--ink-400); flex-shrink: 0; }
.lab-btn { margin-top: 12px; width: 100%; }
.lab-btn:disabled { opacity: .5; }

.vs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.vs-side { text-decoration: none; color: inherit; padding: 10px; border-radius: 10px; background: var(--green-50); cursor: pointer; }
.vs-side b { font-size: 15px; display: block; }
.vs-type { font-size: 11px; color: var(--ink-400); }
.vs-one { font-size: 12px; color: var(--ink-600); margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

.j-line { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }
.j-num { font-size: 20px; color: var(--green-text); }
.duo { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
.duo:last-child { margin-bottom: 0; }
.duo-col h4 { font-size: 12px; color: var(--ink-400); font-weight: 600; margin-bottom: 6px; }
.duo-n { font-size: 13px; margin-bottom: 2px; }
.duo-share { font-size: 12px; color: var(--green-text); margin-top: 6px; line-height: 1.5; }
.duo-share.dim { color: var(--ink-400); }
.chip-wrap { display: flex; flex-wrap: wrap; gap: 4px; }
.tag.gene { font-family: ui-monospace, monospace; font-size: 11px; }
.dim-tag { opacity: .85; }
.hint { font-size: 12px; color: var(--ink-600); margin-top: 8px; line-height: 1.6; }
.hint.ok { color: var(--green-text); }
.hint.warn { color: var(--amber-text); background: var(--amber-50); padding: 8px 10px; border-radius: 8px; }

.radar-card { display: flex; gap: 14px; align-items: center; }
.radar { width: 130px; flex-shrink: 0; }
.radar-side { flex: 1; min-width: 0; }
.legend { font-size: 12px; color: var(--ink-600); margin-bottom: 4px; display: flex; align-items: center; gap: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.dot.a { background: var(--green-600); }
.dot.b { background: var(--amber-600); }
.radar-rows { margin-top: 8px; }
.radar-row { display: flex; align-items: center; gap: 6px; font-size: 12px; padding: 4px 0; border-top: 1px dashed var(--green-100); }
.radar-row span:first-child { color: var(--ink-400); width: 56px; }
.radar-row b { color: var(--green-text); }
.radar-row b.amber { color: var(--amber-text); }
.sep { color: var(--ink-400); font-size: 10px; }

.picker { padding: 16px; }
.picker h3 { font-size: 15px; margin-bottom: 10px; }
.picker-list { max-height: 50vh; overflow-y: auto; }
.picker-item {
  display: flex; flex-direction: column; width: 100%; text-align: left; padding: 10px 12px;
  border: none; background: var(--green-50); border-radius: 10px; margin-bottom: 6px; cursor: pointer;
}
.picker-item.active { background: var(--green-700); }
.picker-item.active .pi-name, .picker-item.active .pi-sub { color: #fff; }
.pi-name { font-size: 14px; font-weight: 600; color: var(--ink-900); }
.pi-sub { font-size: 11px; color: var(--ink-400); margin-top: 2px; }

/* 小屏降级：双列对照叠成单列（320px 下不再挤压） */
@media (max-width: 420px) {
  .vs-grid, .duo { grid-template-columns: 1fr; }
}
.wide-popup { width: min(480px, 90vw); }
</style>
