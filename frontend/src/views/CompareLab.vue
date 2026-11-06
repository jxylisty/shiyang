<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FlaskConical, ArrowLeftRight, AlertTriangle, Search, ExternalLink, Check, Sparkles, RefreshCw } from '@lucide/vue'
import AppIcon from '../components/AppIcon.vue'
import { listRecipes, compareRecipes, matImg } from '../api'
import DisclaimerBanner from '../components/DisclaimerBanner.vue'

const route = useRoute()
const router = useRouter()
const all = ref([])            // 全部方子（选择器数据源）
const aId = ref(Number(route.query.a) || null)
const bId = ref(Number(route.query.b) || null)
const result = ref(null)
const loading = ref(false)
const error = ref('')

const showPicker = ref(null)   // 'a' | 'b' | null：弹出选择器
const pickerSearch = ref('')   // 抽屉内搜索过滤
const imgFailed = ref({})      // 失败图片回退记录

const pickerShow = computed({
  get: () => showPicker.value != null,
  set: (v) => {
    if (!v) {
      showPicker.value = null
      pickerSearch.value = ''
    }
  },
})

// 宽屏居中弹窗，窄屏底部抽屉
const mqWide = window.matchMedia('(min-width: 720px)')
const isWide = ref(mqWide.matches)
const onMq = (e) => { isWide.value = e.matches }
onMounted(() => mqWide.addEventListener('change', onMq))
onUnmounted(() => mqWide.removeEventListener('change', onMq))

function markImgFail(key) {
  imgFailed.value[key] = true
}

// 统一根据方子对象获取封面食材图
function getCoverName(r) {
  if (!r) return ''
  const m = r.materials?.[0]
  return typeof m === 'object' ? (m?.name || '') : (m || '')
}

function getCover(r) {
  const name = getCoverName(r)
  return name ? matImg(name) : ''
}

const aRecipe = computed(() => all.value.find(r => r.id === aId.value))
const bRecipe = computed(() => all.value.find(r => r.id === bId.value))
const ready = computed(() => aId.value && bId.value && aId.value !== bId.value)

// 抽屉方子列表搜索过滤
const filteredAll = computed(() => {
  const kw = pickerSearch.value.trim().toLowerCase()
  if (!kw) return all.value
  return all.value.filter(r => {
    const matchName = r.name.toLowerCase().includes(kw)
    const matchMats = r.materials && r.materials.some(m => {
      const mn = typeof m === 'object' ? m.name : m
      return mn && mn.toLowerCase().includes(kw)
    })
    const matchScene = r.scenes && r.scenes.some(s => s.toLowerCase().includes(kw))
    return matchName || matchMats || matchScene
  })
})

function openPicker(slot) {
  showPicker.value = slot
  pickerSearch.value = ''
}

function pick(id) {
  if (showPicker.value === 'a') aId.value = id
  else bId.value = id
  showPicker.value = null
  pickerSearch.value = ''
  if (ready.value) runCompare()
}

function swapRecipes() {
  if (!aId.value && !bId.value) return
  const tmp = aId.value
  aId.value = bId.value
  bId.value = tmp
  if (ready.value) runCompare()
}

onMounted(async () => {
  try {
    all.value = (await listRecipes({ size: 100 })).data.data.items
  } catch {
    error.value = '方子列表加载失败'
  }
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
  } finally {
    loading.value = false
  }
}

const pct = (j) => Math.round(j * 100)
const radarNames = ['入血潜力', '多靶协同', '证据强度']
const radarMax = computed(() => {
  const vals = [...(result.value?.radar.a || []), ...(result.value?.radar.b || [])].filter(v => v != null)
  return Math.max(100, ...vals)
})

function poly(vals) {
  const n = radarNames.length
  return vals.map((v, i) => {
    const r = ((v ?? 0) / radarMax.value) * 52
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / n
    return `${(60 + r * Math.cos(ang)).toFixed(1)},${(60 + r * Math.sin(ang)).toFixed(1)}`
  }).join(' ')
}

// 配料对照计算：共有、仅A、仅B
const sharedMaterialNames = computed(() => {
  if (!result.value?.conflicts?.shared_materials) return new Set()
  return new Set(result.value.conflicts.shared_materials.map(m => m.name))
})

const onlyAMaterials = computed(() => {
  if (!result.value?.a?.materials) return []
  return result.value.a.materials.filter(m => !sharedMaterialNames.value.has(m.name))
})

const onlyBMaterials = computed(() => {
  if (!result.value?.b?.materials) return []
  return result.value.b.materials.filter(m => !sharedMaterialNames.value.has(m.name))
})
</script>

<template>
  <div class="page compare-lab-page">
    <!-- 顶部对决擂台槽位卡片 -->
    <div class="card head-card">
      <div class="lab-badge">
        <FlaskConical :size="14" :stroke-width="2.4" />
        <span>科学药研</span>
      </div>
      <h2 class="lab-title">食养对比实验室</h2>
      <p class="lab-sub">两方并排比对：配料差异、成分覆盖、PU-Learning 入血重叠与生物靶点通路</p>

      <!-- 双槽位擂台对决 -->
      <div class="arena-wrap">
        <!-- 槽位 A -->
        <div class="arena-slot" :class="{ filled: aRecipe }" @click="openPicker('a')">
          <div class="slot-badge a-badge">方子 A</div>
          <template v-if="aRecipe">
            <div class="slot-thumb">
              <img v-if="getCover(aRecipe) && !imgFailed['a_' + aRecipe.id]"
                   :src="getCover(aRecipe)"
                   :alt="aRecipe.name"
                   loading="lazy"
                   @error="markImgFail('a_' + aRecipe.id)" />
              <span v-else class="slot-thumb-fb">
                <AppIcon :name="aRecipe.type === '药膳' ? 'dish' : 'tea'" :size="24" />
              </span>
            </div>
            <div class="slot-meta">
              <b class="slot-name">{{ aRecipe.name }}</b>
              <div class="slot-tags">
                <span class="slot-type">{{ aRecipe.type }}</span>
                <span class="slot-mcount">{{ aRecipe.materials?.length || 0 }} 味配料</span>
              </div>
            </div>
            <span class="slot-action">更换</span>
          </template>
          <template v-else>
            <div class="slot-empty">
              <span class="slot-plus">+</span>
              <span class="slot-empty-text">选择方子 A</span>
            </div>
          </template>
        </div>

        <!-- 中间 VS / 互换按钮 -->
        <button class="arena-vs" @click.stop="swapRecipes" title="点击互换双方位置">
          <span class="vs-text">VS</span>
          <ArrowLeftRight :size="14" class="vs-icon" />
        </button>

        <!-- 槽位 B -->
        <div class="arena-slot" :class="{ filled: bRecipe }" @click="openPicker('b')">
          <div class="slot-badge b-badge">方子 B</div>
          <template v-if="bRecipe">
            <div class="slot-thumb">
              <img v-if="getCover(bRecipe) && !imgFailed['b_' + bRecipe.id]"
                   :src="getCover(bRecipe)"
                   :alt="bRecipe.name"
                   loading="lazy"
                   @error="markImgFail('b_' + bRecipe.id)" />
              <span v-else class="slot-thumb-fb">
                <AppIcon :name="bRecipe.type === '药膳' ? 'dish' : 'tea'" :size="24" />
              </span>
            </div>
            <div class="slot-meta">
              <b class="slot-name">{{ bRecipe.name }}</b>
              <div class="slot-tags">
                <span class="slot-type">{{ bRecipe.type }}</span>
                <span class="slot-mcount">{{ bRecipe.materials?.length || 0 }} 味配料</span>
              </div>
            </div>
            <span class="slot-action">更换</span>
          </template>
          <template v-else>
            <div class="slot-empty">
              <span class="slot-plus">+</span>
              <span class="slot-empty-text">选择方子 B</span>
            </div>
          </template>
        </div>
      </div>

      <button class="btn lab-btn" :disabled="!ready || loading" @click="runCompare">
        <FlaskConical v-if="!loading" :size="15" />
        <RefreshCw v-else :size="15" class="spin-icon" />
        {{ loading ? '深入对比分析中…' : (!ready ? '请选定两个不同方子' : '开始对比') }}
      </button>
    </div>

    <van-empty v-if="error" image="error" :description="error" />

    <!-- 对比分析结果呈现 -->
    <template v-if="result">
      <!-- 双方头部概览卡片（带封面图和链接） -->
      <div class="card vs-hero-card">
        <div class="vs-hero-grid">
          <!-- A 方 -->
          <router-link class="vs-hero-item side-a" :to="`/recipes/${result.a.id}`" title="查看方子 A 详情">
            <div class="vsh-img-box">
              <img v-if="getCover(result.a) && !imgFailed['vsh_a_' + result.a.id]"
                   :src="getCover(result.a)"
                   :alt="result.a.name"
                   loading="lazy"
                   @error="markImgFail('vsh_a_' + result.a.id)" />
              <span v-else class="vsh-img-fb">
                <AppIcon :name="result.a.type === '药膳' ? 'dish' : 'tea'" :size="32" />
              </span>
              <span class="vsh-side-tag tag-a">方子 A</span>
            </div>
            <div class="vsh-body">
              <div class="vsh-title-row">
                <b>{{ result.a.name }}</b>
                <ExternalLink :size="13" class="vsh-ext" />
              </div>
              <div class="vsh-meta">
                <span class="tag warm">{{ result.a.type }}</span>
                <span>{{ result.a.materials.length }} 味配料</span>
              </div>
              <p class="vsh-one">{{ result.a.oneliner }}</p>
            </div>
          </router-link>

          <!-- B 方 -->
          <router-link class="vs-hero-item side-b" :to="`/recipes/${result.b.id}`" title="查看方子 B 详情">
            <div class="vsh-img-box">
              <img v-if="getCover(result.b) && !imgFailed['vsh_b_' + result.b.id]"
                   :src="getCover(result.b)"
                   :alt="result.b.name"
                   loading="lazy"
                   @error="markImgFail('vsh_b_' + result.b.id)" />
              <span v-else class="vsh-img-fb">
                <AppIcon :name="result.b.type === '药膳' ? 'dish' : 'tea'" :size="32" />
              </span>
              <span class="vsh-side-tag tag-b">方子 B</span>
            </div>
            <div class="vsh-body">
              <div class="vsh-title-row">
                <b>{{ result.b.name }}</b>
                <ExternalLink :size="13" class="vsh-ext" />
              </div>
              <div class="vsh-meta">
                <span class="tag warm">{{ result.b.type }}</span>
                <span>{{ result.b.materials.length }} 味配料</span>
              </div>
              <p class="vsh-one">{{ result.b.oneliner }}</p>
            </div>
          </router-link>
        </div>
      </div>

      <!-- 配料横向对照（图文并茂） -->
      <div class="section-title">配料对照</div>
      <div class="card mat-compare-card">
        <!-- 共有配料 -->
        <div v-if="result.conflicts?.shared_materials?.length" class="mcp-block">
          <div class="mcp-subhead">
            <span class="mcp-dot shared-dot"></span>
            <b>共有配料（{{ result.conflicts.shared_materials.length }} 味）</b>
            <span class="mcp-subhint">同日饮用两方时注意克重叠加</span>
          </div>
          <div class="mcp-grid">
            <div v-for="m in result.conflicts.shared_materials" :key="m.name" class="mcp-chip shared">
              <img v-if="!imgFailed['m_s_' + m.name]"
                   :src="matImg(m.name)"
                   :alt="m.name"
                   class="mcp-img"
                   loading="lazy"
                   @error="markImgFail('m_s_' + m.name)" />
              <div class="mcp-info">
                <b class="mcp-name">{{ m.name }}</b>
                <span class="mcp-grams" v-if="m.total != null">
                  A: {{ m.grams_a }}g · B: {{ m.grams_b }}g (合计 {{ m.total }}g)
                </span>
                <span class="mcp-grams dim" v-else>克重未完整标注</span>
              </div>
            </div>
          </div>
        </div>
        <p v-else class="hint ok-hint">两方无共有配料，食材构成完全互补</p>

        <!-- 各自专属配料对照 -->
        <div class="mcp-columns">
          <!-- 仅 A -->
          <div class="mcp-col">
            <div class="mcp-col-head a-head">
              <span>仅 {{ result.a.name }} 独有（{{ onlyAMaterials.length }} 味）</span>
            </div>
            <div class="mcp-chip-list">
              <div v-for="m in onlyAMaterials" :key="m.name" class="mcp-mini-chip">
                <img v-if="!imgFailed['m_a_' + m.name]"
                     :src="matImg(m.name)"
                     :alt="m.name"
                     class="mcp-mini-img"
                     loading="lazy"
                     @error="markImgFail('m_a_' + m.name)" />
                <span class="mcp-mini-name">{{ m.name }}</span>
                <span v-if="m.grams" class="mcp-mini-g">{{ m.grams }}g</span>
              </div>
              <span v-if="!onlyAMaterials.length" class="mcp-empty-hint">全部配料均为共有</span>
            </div>
          </div>

          <!-- 仅 B -->
          <div class="mcp-col">
            <div class="mcp-col-head b-head">
              <span>仅 {{ result.b.name }} 独有（{{ onlyBMaterials.length }} 味）</span>
            </div>
            <div class="mcp-chip-list">
              <div v-for="m in onlyBMaterials" :key="m.name" class="mcp-mini-chip">
                <img v-if="!imgFailed['m_b_' + m.name]"
                     :src="matImg(m.name)"
                     :alt="m.name"
                     class="mcp-mini-img"
                     loading="lazy"
                     @error="markImgFail('m_b_' + m.name)" />
                <span class="mcp-mini-name">{{ m.name }}</span>
                <span v-if="m.grams" class="mcp-mini-g">{{ m.grams }}g</span>
              </div>
              <span v-if="!onlyBMaterials.length" class="mcp-empty-hint">全部配料均为共有</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 成分重叠 -->
      <div class="section-title">成分重叠分析</div>
      <div class="card">
        <div class="metric-meter-box">
          <div class="meter-head">
            <div class="meter-title">
              <span>活性成分 Jaccard 重叠度</span>
              <span class="tag" :class="{ warm: pct(result.compound.jaccard) > 30 }">{{ result.compound.overlap_label }}</span>
            </div>
            <b class="meter-value">{{ pct(result.compound.jaccard) }}%</b>
          </div>
          <div class="meter-track">
            <div class="meter-fill" :style="{ width: `${Math.min(100, pct(result.compound.jaccard))}%` }"></div>
          </div>
        </div>

        <div class="duo">
          <div class="duo-col">
            <h4>高入血活性成分（PU-Learning 预测 ≥70%）</h4>
            <div class="blood-stats">
              <div class="blood-stat-badge">A「{{ result.a.name }}」：<b>{{ result.compound.hi_blood_a.length }}</b> 个</div>
              <div class="blood-stat-badge b-stat">B「{{ result.b.name }}」：<b>{{ result.compound.hi_blood_b.length }}</b> 个</div>
            </div>
            <p class="duo-share" v-if="result.compound.hi_blood_shared.length">
              双方共同高入血成分（{{ result.compound.hi_blood_shared.length }} 个）：{{ result.compound.hi_blood_shared.slice(0, 8).join('、') }}<span v-if="result.compound.hi_blood_shared.length > 8"> 等</span>
            </p>
            <p class="duo-share dim" v-else>无共同高入血成分，表明两方在体内的药效作用靶向可能具有显著差异</p>
          </div>
        </div>

        <div class="duo" v-if="result.compound.shared.length">
          <div class="duo-col">
            <h4>双方共同活性成分（{{ result.compound.shared.length }} 种）</h4>
            <div class="chip-wrap">
              <span v-for="n in result.compound.shared" :key="n" class="tag shared-chip">{{ n }}</span>
            </div>
          </div>
        </div>

        <div class="duo">
          <div class="duo-col">
            <h4>仅 A 有的代表成分（共 {{ result.compound.only_a.length }} 种）</h4>
            <div class="chip-wrap">
              <span v-for="n in result.compound.only_a.slice(0, 10)" :key="n" class="tag dim-tag">{{ n }}</span>
            </div>
          </div>
          <div class="duo-col">
            <h4>仅 B 有的代表成分（共 {{ result.compound.only_b.length }} 种）</h4>
            <div class="chip-wrap">
              <span v-for="n in result.compound.only_b.slice(0, 10)" :key="n" class="tag dim-tag">{{ n }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 靶点与通路 -->
      <div class="section-title">作用靶点与通路</div>
      <div class="card">
        <div class="metric-meter-box">
          <div class="meter-head">
            <div class="meter-title">
              <span>作用靶点重叠度</span>
              <span class="tag">{{ result.target.overlap_label }}</span>
            </div>
            <b class="meter-value">{{ pct(result.target.jaccard) }}%</b>
          </div>
          <div class="meter-track">
            <div class="meter-fill target-fill" :style="{ width: `${Math.min(100, pct(result.target.jaccard))}%` }"></div>
          </div>
        </div>

        <p class="hint">A 覆盖 {{ result.target.only_a.length + result.target.shared.length }} 个靶点，B 覆盖 {{ result.target.only_b.length + result.target.shared.length }} 个</p>
        <div v-if="result.target.shared.length" class="chip-wrap gene-wrap">
          <span v-for="g in result.target.shared" :key="g" class="tag gene">{{ g }}</span>
        </div>
        <p v-else class="hint dim-hint">两者核心靶点无重合，生物作用通路完全独立</p>
      </div>

      <!-- 食养科学三维指数对照 -->
      <div class="section-title">食养科学三维机制对照</div>
      <div class="card radar-card">
        <div class="radar-box">
          <svg viewBox="0 0 120 120" class="radar">
            <polygon points="60,8 112,60 60,112 8,60" fill="none" stroke="var(--green-100)" />
            <polygon points="60,34 86,60 60,86 34,60" fill="none" stroke="var(--green-100)" />
            <polygon :points="poly(result.radar.a)" fill="rgba(53,144,104,.2)" stroke="var(--green-600)" stroke-width="1.8" />
            <polygon :points="poly(result.radar.b)" fill="rgba(201,138,45,.2)" stroke="var(--amber-600)" stroke-width="1.8" stroke-dasharray="4 2" />
          </svg>
          <div class="radar-legends">
            <div class="legend"><i class="dot a" />{{ result.a.name }}</div>
            <div class="legend"><i class="dot b" />{{ result.b.name }}</div>
          </div>
        </div>

        <div class="radar-side">
          <div class="radar-rows">
            <div v-for="(name, i) in radarNames" :key="name" class="radar-row">
              <span class="rr-name">{{ name }}</span>
              <div class="rr-bar-box">
                <div class="rr-bar a-bar" :style="{ width: `${Math.min(100, (result.radar.a[i] || 0))}%` }">
                  <span class="rr-val">{{ result.radar.a[i]?.toFixed(0) ?? '—' }}</span>
                </div>
                <div class="rr-bar b-bar" :style="{ width: `${Math.min(100, (result.radar.b[i] || 0))}%` }">
                  <span class="rr-val">{{ result.radar.b[i]?.toFixed(0) ?? '—' }}</span>
                </div>
              </div>
            </div>
          </div>
          <p class="radar-note">基于 PU-Learning 入血预测、靶点网络协同度与药食同源/实验证据分级（满分 100）。</p>
        </div>
      </div>

      <!-- 体质适宜对照 -->
      <div class="section-title">体质适宜对照</div>
      <div class="card">
        <div class="duo">
          <div class="duo-col">
            <h4>{{ result.a.name }} 适宜</h4>
            <div class="chip-wrap">
              <span v-for="c in result.a.constitutions_suitable" :key="c" class="tag ok-tag">{{ c }}</span>
            </div>
          </div>
          <div class="duo-col">
            <h4>{{ result.b.name }} 适宜</h4>
            <div class="chip-wrap">
              <span v-for="c in result.b.constitutions_suitable" :key="c" class="tag ok-tag">{{ c }}</span>
            </div>
          </div>
        </div>

        <p v-if="result.constitution.both_suitable.length" class="hint ok">
          两者都适合：{{ result.constitution.both_suitable.join('、') }} 体质，可按具体场景任选
        </p>
        <p v-if="result.constitution.warn_a.length || result.constitution.warn_b.length" class="hint warn">
          <AlertTriangle :size="13" style="vertical-align: -2px" />
          注意：{{ result.constitution.warn_a.length ? `${result.a.name} 不宜 ${result.constitution.warn_a.join('、')}体质；` : '' }}
          {{ result.constitution.warn_b.length ? `${result.b.name} 不宜 ${result.constitution.warn_b.join('、')}体质` : '' }}
        </p>
      </div>

      <!-- 慢病安全与同饮注意 -->
      <template v-if="result.conflicts && (result.conflicts.shared_materials.length || result.conflicts.safety.length)">
        <div class="section-title">同饮安全须知</div>
        <div class="card">
          <template v-if="result.conflicts.shared_materials.length">
            <h4 class="cf-h">共有配料克重叠加注意</h4>
            <div v-for="m in result.conflicts.shared_materials" :key="m.name" class="cf-row">
              <span class="cf-name">{{ m.name }}</span>
              <span class="cf-g">
                <template v-if="m.total != null">{{ m.grams_a }}g + {{ m.grams_b }}g = <b>合计 {{ m.total }}g</b></template>
                <template v-else>两方用量未完整标注</template>
              </span>
            </div>
            <p class="hint warn">
              <AlertTriangle :size="13" style="vertical-align: -2px" />
              同日饮用两方时上述配料用量将累加，请酌情减半或隔开时段饮用；若有慢性病或特殊体质请咨询执业医师。
            </p>
          </template>

          <template v-if="result.conflicts.safety.length">
            <h4 class="cf-h" style="margin-top: 14px;">慢病/特殊人群禁忌</h4>
            <div v-for="s in result.conflicts.safety" :key="s.profile" class="cf-profile">
              <span class="tag" :class="{ 'cf-block': [s.a?.verdict, s.b?.verdict].includes('block') }">{{ s.profile_name }}</span>
              <span class="cf-detail">
                <template v-if="s.a && s.a.verdict !== 'pass'">A「{{ result.a.name }}」{{ s.a.verdict === 'block' ? '不建议' : '需注意' }}（{{ [...s.a.blocks, ...s.a.warns].map(x => x.material).slice(0, 3).join('、') }}）</template>
                <template v-if="s.b && s.b.verdict !== 'pass'">B「{{ result.b.name }}」{{ s.b.verdict === 'block' ? '不建议' : '需注意' }}（{{ [...s.b.blocks, ...s.b.warns].map(x => x.material).slice(0, 3).join('、') }}）</template>
              </span>
            </div>
            <p class="hint">人群禁忌基于《中国药典》及药食同源安全通识规则整理，仅供科学参考。</p>
          </template>
        </div>
      </template>
    </template>

    <!-- 选择方子抽屉（带食材图、类型胶囊与实时搜索） -->
    <van-popup :show="pickerShow" @update:show="pickerShow = $event"
               :position="isWide ? 'center' : 'bottom'"
               round
               :class="{ 'wide-popup': isWide }"
               :style="{ maxHeight: '75%' }">
      <div class="picker">
        <div class="picker-head">
          <h3>选择方子 {{ showPicker === 'a' ? 'A' : 'B' }}</h3>
          <span class="picker-count">共 {{ filteredAll.length }} 款可选</span>
        </div>

        <!-- 搜索过滤 -->
        <div class="picker-search-wrap">
          <Search :size="14" class="ps-icon" />
          <input v-model="pickerSearch" type="text" placeholder="搜索方子名称、配料或适用场景…" class="picker-search-input" />
        </div>

        <div class="picker-list">
          <button v-for="r in filteredAll" :key="r.id" class="picker-item"
                  :class="{ active: (showPicker === 'a' ? aId : bId) === r.id }"
                  @click="pick(r.id)">
            <div class="pi-thumb">
              <img v-if="getCover(r) && !imgFailed['p_' + r.id]"
                   :src="getCover(r)"
                   :alt="r.name"
                   loading="lazy"
                   @error="markImgFail('p_' + r.id)" />
              <span v-else class="pi-thumb-fb">
                <AppIcon :name="r.type === '药膳' ? 'dish' : 'tea'" :size="20" />
              </span>
            </div>
            <div class="pi-body">
              <div class="pi-row">
                <span class="pi-name">{{ r.name }}</span>
                <span class="tag warm pi-tag">{{ r.type }}</span>
              </div>
              <span class="pi-sub">
                <template v-if="r.scenes?.length">{{ r.scenes[0] }} · </template>
                <template v-if="r.materials?.length">配料：{{ r.materials.slice(0, 3).join('、') }}</template>
              </span>
            </div>
            <Check v-if="(showPicker === 'a' ? aId : bId) === r.id" :size="16" class="pi-check" />
          </button>
          <div v-if="!filteredAll.length" class="picker-empty">
            没有匹配的方子，换个关键词搜搜看
          </div>
        </div>
      </div>
    </van-popup>

    <DisclaimerBanner variant="recipe" style="margin-top: 16px;" />
  </div>
</template>

<style scoped>
.compare-lab-page { padding-bottom: 24px; }
.head-card { text-align: center; padding: 22px 16px; position: relative; }

.lab-badge {
  display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px;
  background: var(--green-50); border: 1px solid var(--green-100);
  border-radius: 12px; font-size: 11.5px; color: var(--green-text);
  font-weight: 600; margin-bottom: 8px;
}
.lab-title {
  font-family: var(--font-serif); font-size: 21px; font-weight: 700;
  color: var(--green-text); letter-spacing: 0.5px; margin: 0;
}
.lab-sub {
  font-size: 12px; color: var(--ink-400); margin: 6px auto 18px;
  max-width: 440px; line-height: 1.5;
}

/* 擂台对决槽位 */
.arena-wrap {
  display: flex; align-items: center; gap: 10px; margin-bottom: 14px;
}
.arena-slot {
  flex: 1; min-width: 0; min-height: 82px; border-radius: 14px;
  border: 1.5px dashed var(--green-100); background: var(--green-50);
  padding: 10px; cursor: pointer; position: relative; text-align: left;
  display: flex; align-items: center; gap: 10px; transition: all 0.2s ease;
}
.arena-slot:hover {
  border-color: var(--green-400); background: #fbfdfc;
}
.arena-slot.filled {
  border: 1px solid rgba(58, 122, 94, 0.25); background: var(--card);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

.slot-badge {
  position: absolute; top: -8px; left: 10px; font-size: 10px; font-weight: 700;
  padding: 1px 7px; border-radius: 6px; letter-spacing: 0.3px;
}
.a-badge { background: var(--green-600); color: #fff; }
.b-badge { background: var(--amber-600); color: #fff; }

.slot-thumb {
  width: 48px; height: 48px; border-radius: 10px; overflow: hidden;
  background: var(--green-50); flex-shrink: 0; border: 1px solid rgba(0,0,0,0.04);
}
.slot-thumb img { width: 100%; height: 100%; object-fit: cover; }
.slot-thumb-fb {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  color: var(--green-600);
}

.slot-meta { flex: 1; min-width: 0; }
.slot-name {
  font-size: 14.5px; font-family: var(--font-serif); font-weight: 700;
  color: var(--ink-900); display: block; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.slot-tags { display: flex; align-items: center; gap: 6px; margin-top: 3px; }
.slot-type {
  font-size: 10.5px; padding: 1px 5px; border-radius: 4px;
  background: var(--amber-50); color: var(--amber-text);
}
.slot-mcount { font-size: 11px; color: var(--ink-400); }
.slot-action { font-size: 11px; color: var(--green-text); flex-shrink: 0; }

.slot-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  width: 100%; gap: 3px; color: var(--ink-400);
}
.slot-plus { font-size: 20px; font-weight: 300; line-height: 1; color: var(--green-600); }
.slot-empty-text { font-size: 12.5px; font-weight: 500; }

.arena-vs {
  width: 38px; height: 38px; border-radius: 50%; border: 1px solid var(--green-100);
  background: #fff; display: flex; flex-direction: column; align-items: center;
  justify-content: center; flex-shrink: 0; cursor: pointer; color: var(--ink-600);
  box-shadow: 0 2px 6px rgba(0,0,0,0.05); transition: transform 0.2s ease;
}
.arena-vs:hover { transform: scale(1.08) rotate(180deg); color: var(--green-text); }
.vs-text { font-size: 9px; font-weight: 800; line-height: 1; color: var(--green-text); }
.vs-icon { margin-top: 1px; color: var(--ink-400); }

.lab-btn {
  width: 100%; padding: 11px; font-size: 14.5px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  border-radius: 12px;
}
.spin-icon { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* 双方概览卡片 */
.vs-hero-card { padding: 14px; }
.vs-hero-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.vs-hero-item {
  text-decoration: none; color: inherit; display: flex; flex-direction: column;
  padding: 12px; border-radius: 12px; background: var(--green-50);
  border: 1px solid rgba(58, 122, 94, 0.12); position: relative;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.vs-hero-item:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
.side-a { background: linear-gradient(180deg, rgba(239, 246, 242, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%); }
.side-b { background: linear-gradient(180deg, rgba(253, 248, 238, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%); }

.vsh-img-box {
  width: 100%; height: 86px; border-radius: 9px; overflow: hidden;
  position: relative; background: #eaf2ed; margin-bottom: 8px;
}
.vsh-img-box img { width: 100%; height: 100%; object-fit: cover; }
.vsh-img-fb {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  color: var(--green-600);
}
.vsh-side-tag {
  position: absolute; bottom: 6px; left: 6px; font-size: 10px; font-weight: 700;
  padding: 2px 7px; border-radius: 5px; color: #fff;
}
.tag-a { background: var(--green-600); }
.tag-b { background: var(--amber-600); }

.vsh-title-row {
  display: flex; align-items: center; justify-content: space-between; gap: 4px;
}
.vsh-title-row b {
  font-size: 15px; font-family: var(--font-serif); color: var(--ink-900);
}
.vsh-ext { color: var(--ink-400); flex-shrink: 0; }
.vsh-meta { display: flex; align-items: center; gap: 6px; margin: 4px 0; font-size: 11px; color: var(--ink-400); }
.vsh-one {
  font-size: 12px; color: var(--ink-600); margin: 4px 0 0; line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}

/* 配料对照 */
.mat-compare-card { padding: 16px; }
.mcp-block { margin-bottom: 16px; }
.mcp-subhead {
  display: flex; align-items: center; gap: 6px; margin-bottom: 10px; font-size: 13px;
}
.mcp-dot { width: 8px; height: 8px; border-radius: 50%; }
.shared-dot { background: var(--green-600); }
.mcp-subhint { font-size: 11px; color: var(--ink-400); margin-left: auto; }

.mcp-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px;
}
.mcp-chip {
  display: flex; align-items: center; gap: 8px; padding: 7px 10px;
  border-radius: 10px; background: var(--green-50); border: 1px solid var(--green-100);
}
.mcp-img {
  width: 32px; height: 32px; border-radius: 7px; object-fit: cover; flex-shrink: 0;
  background: #fff; border: 1px solid rgba(0,0,0,0.04);
}
.mcp-info { min-width: 0; }
.mcp-name { font-size: 13px; color: var(--ink-900); display: block; }
.mcp-grams { font-size: 11px; color: var(--green-text); }
.mcp-grams.dim { color: var(--ink-400); }

.mcp-columns {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
  border-top: 1px dashed var(--green-100); padding-top: 14px;
}
.mcp-col-head {
  font-size: 12px; font-weight: 600; margin-bottom: 8px; padding-bottom: 4px;
  border-bottom: 1.5px solid transparent;
}
.a-head { color: var(--green-text); border-color: var(--green-600); }
.b-head { color: var(--amber-text); border-color: var(--amber-600); }

.mcp-chip-list { display: flex; flex-direction: column; gap: 6px; }
.mcp-mini-chip {
  display: flex; align-items: center; gap: 6px; padding: 5px 8px;
  border-radius: 8px; background: rgba(0,0,0,0.02); font-size: 12px;
}
.mcp-mini-img {
  width: 24px; height: 24px; border-radius: 5px; object-fit: cover; flex-shrink: 0;
}
.mcp-mini-name { color: var(--ink-800); font-weight: 500; }
.mcp-mini-g { font-size: 11px; color: var(--ink-400); margin-left: auto; }
.mcp-empty-hint { font-size: 11px; color: var(--ink-400); padding: 4px 0; }
.ok-hint { font-size: 12px; color: var(--green-text); background: var(--green-50); padding: 8px; border-radius: 8px; margin-bottom: 14px; }

/* 能量仪表条 */
.metric-meter-box { margin-bottom: 14px; }
.meter-head {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;
}
.meter-title { display: flex; align-items: center; gap: 8px; font-size: 13.5px; font-weight: 600; color: var(--ink-800); }
.meter-value { font-size: 21px; color: var(--green-text); font-variant-numeric: tabular-nums; }
.meter-track {
  width: 100%; height: 8px; background: var(--green-50); border-radius: 99px; overflow: hidden;
  border: 1px solid var(--green-100);
}
.meter-fill {
  height: 100%; background: linear-gradient(90deg, var(--green-400) 0%, var(--green-600) 100%);
  border-radius: 99px; transition: width 0.6s ease;
}
.meter-fill.target-fill {
  background: linear-gradient(90deg, var(--green-500) 0%, #308365 100%);
}

.duo { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.duo:last-child { margin-bottom: 0; }
.duo-col h4 { font-size: 12px; color: var(--ink-400); font-weight: 600; margin-bottom: 6px; }

.blood-stats { display: flex; flex-direction: column; gap: 4px; margin-bottom: 6px; }
.blood-stat-badge {
  font-size: 12px; padding: 4px 8px; border-radius: 6px; background: var(--green-50); color: var(--green-text);
}
.blood-stat-badge.b-stat { background: var(--amber-50); color: var(--amber-text); }
.duo-share { font-size: 12px; color: var(--green-text); margin-top: 6px; line-height: 1.5; }
.duo-share.dim { color: var(--ink-400); }

.chip-wrap { display: flex; flex-wrap: wrap; gap: 4px; }
.shared-chip { background: var(--green-100); color: var(--green-text); font-weight: 500; }
.dim-tag { opacity: .85; }
.tag.gene { font-family: ui-monospace, monospace; font-size: 11px; background: #f3f6f4; color: var(--green-text); }
.hint { font-size: 12px; color: var(--ink-600); margin-top: 8px; line-height: 1.6; }
.hint.ok { color: var(--green-text); }
.hint.warn { color: var(--amber-text); background: var(--amber-50); padding: 8px 10px; border-radius: 8px; }
.ok-tag { background: var(--green-50); color: var(--green-text); }

/* 雷达与指标槽 */
.radar-card { display: flex; gap: 16px; align-items: center; }
.radar-box { width: 130px; flex-shrink: 0; text-align: center; }
.radar { width: 120px; height: 120px; }
.radar-legends { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; }
.legend {
  font-size: 11px; color: var(--ink-600); display: flex; align-items: center; justify-content: center;
  gap: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot.a { background: var(--green-600); }
.dot.b { background: var(--amber-600); }

.radar-side { flex: 1; min-width: 0; }
.radar-rows { display: flex; flex-direction: column; gap: 8px; }
.radar-row { font-size: 12px; }
.rr-name { font-size: 11.5px; color: var(--ink-600); margin-bottom: 3px; display: block; }
.rr-bar-box { display: flex; flex-direction: column; gap: 3px; }
.rr-bar {
  height: 14px; border-radius: 4px; display: flex; align-items: center;
  padding: 0 6px; min-width: 28px; transition: width 0.5s ease;
}
.a-bar { background: var(--green-600); }
.b-bar { background: var(--amber-600); }
.rr-val { font-size: 9.5px; color: #fff; font-weight: 700; }
.radar-note { font-size: 10.5px; color: var(--ink-400); margin-top: 10px; line-height: 1.45; }

/* 同饮冲突 */
.cf-h { font-size: 12px; color: var(--ink-400); font-weight: 600; margin: 4px 0 8px; }
.cf-row {
  display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
  font-size: 13px; padding: 6px 0; border-top: 1px dashed var(--green-100);
}
.cf-name { font-weight: 600; color: var(--ink-900); }
.cf-g { font-size: 12px; color: var(--ink-600); text-align: right; }
.cf-profile { display: flex; gap: 8px; align-items: flex-start; padding: 7px 0; border-top: 1px dashed var(--green-100); }
.cf-profile .tag { flex-shrink: 0; margin-top: 1px; }
.cf-profile .tag.cf-block { background: var(--amber-50); color: var(--amber-text); }
.cf-detail { font-size: 12px; color: var(--ink-600); line-height: 1.6; display: flex; flex-direction: column; gap: 2px; }

/* 抽屉选择器 */
.picker { padding: 16px; }
.picker-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.picker-head h3 { font-size: 16px; margin: 0; font-family: var(--font-serif); color: var(--green-text); }
.picker-count { font-size: 12px; color: var(--ink-400); }

.picker-search-wrap {
  display: flex; align-items: center; gap: 6px; padding: 7px 10px;
  background: var(--green-50); border: 1px solid var(--green-100);
  border-radius: 9px; margin-bottom: 12px;
}
.ps-icon { color: var(--ink-400); flex-shrink: 0; }
.picker-search-input {
  border: none; background: transparent; width: 100%; font-size: 13px;
  outline: none; color: var(--ink-900);
}

.picker-list { max-height: 52vh; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.picker-item {
  display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
  padding: 8px 10px; border: 1px solid rgba(0,0,0,0.03); background: var(--green-50);
  border-radius: 10px; cursor: pointer; transition: all 0.15s ease;
}
.picker-item:hover { background: #eaf3ed; border-color: var(--green-200); }
.picker-item.active { background: var(--green-700); border-color: var(--green-700); }
.picker-item.active .pi-name { color: #fff; }
.picker-item.active .pi-sub { color: rgba(255,255,255,0.8); }
.picker-item.active .pi-tag { background: rgba(255,255,255,0.2); color: #fff; }

.pi-thumb {
  width: 44px; height: 44px; border-radius: 8px; overflow: hidden;
  background: #fff; flex-shrink: 0; border: 1px solid rgba(0,0,0,0.04);
}
.pi-thumb img { width: 100%; height: 100%; object-fit: cover; }
.pi-thumb-fb {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  color: var(--green-600);
}

.pi-body { flex: 1; min-width: 0; }
.pi-row { display: flex; align-items: center; gap: 6px; }
.pi-name { font-size: 14px; font-weight: 600; color: var(--ink-900); }
.pi-tag { font-size: 10.5px; }
.pi-sub {
  font-size: 11px; color: var(--ink-400); margin-top: 2px; display: block;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pi-check { color: #fff; flex-shrink: 0; }
.picker-empty { text-align: center; font-size: 12.5px; color: var(--ink-400); padding: 24px 0; }

.wide-popup { width: min(520px, 92vw); }

@media (max-width: 480px) {
  .vs-hero-grid, .duo, .mcp-columns { grid-template-columns: 1fr; }
  .arena-wrap { flex-direction: column; }
  .arena-vs { margin: -4px 0; }
  .radar-card { flex-direction: column; }
}
</style>
