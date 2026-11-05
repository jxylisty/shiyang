<script setup>
import { ref, computed, onMounted } from 'vue'
import { ShoppingBasket, Sparkles, Search } from '@lucide/vue'
import { showSuccessToast } from 'vant'
import { getPantryMaterials, pantryMatch, matImg, analyzeCustomRecipe } from '../api'
import DisclaimerBanner from '../components/DisclaimerBanner.vue'

const activeTab = ref('own')  // 'own' = 我的茶罐 / 'custom' = 自定义鉴方
const materials = ref([])       // 全部可选食材
const selected = ref(new Set()) // 勾选的食材名
const search = ref('')
const result = ref(null)
const loading = ref(false)
const error = ref('')

const STORE_KEY = 'shiyang_pantry_v1'

onMounted(async () => {
  // 本地记忆：上次勾选的茶罐
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || '[]')
    saved.forEach(n => selected.value.add(n))
  } catch { /* ignore */ }
  try {
    materials.value = (await getPantryMaterials()).data.data.items
  } catch { error.value = '食材清单加载失败' }
  if (selected.value.size) runMatch()
})

const shown = computed(() => {
  const kw = search.value.trim()
  const sel = [...selected.value]
  const rest = materials.value.filter(m => !selected.value.has(m.name))
  const pool = kw ? rest.filter(m => m.name.includes(kw)) : rest
  return { sel, pool: pool.slice(0, kw ? 50 : 40) }
})

function toggle(name) {
  const s = new Set(selected.value)
  s.has(name) ? s.delete(name) : s.add(name)
  selected.value = s
}

function persist() {
  localStorage.setItem(STORE_KEY, JSON.stringify([...selected.value]))
}

async function runMatch() {
  if (!selected.value.size) { result.value = null; return }
  loading.value = true
  error.value = ''
  persist()
  try {
    result.value = (await pantryMatch([...selected.value])).data.data
  } catch { error.value = '匹配失败，请重试' } finally { loading.value = false }
}

function coverBar(c) { return Math.round(c * 100) }

// ============ 自定义鉴方 ============
const customHerbs = ref([])  // [{name, grams}]
const customInput = ref('')
const customLoading = ref(false)
const customError = ref('')
const customResult = ref(null)

const customCanAnalyze = computed(() =>
  customHerbs.value.length > 0 && customHerbs.value.every(h => h.name.trim()))

function addCustomHerb() {
  const name = customInput.value.trim()
  if (!name) return
  // 避免重复
  if (customHerbs.value.some(h => h.name === name)) {
    customInput.value = ''
    return
  }
  customHerbs.value.push({ name, grams: null })
  customInput.value = ''
}

function removeCustomHerb(idx) {
  customHerbs.value.splice(idx, 1)
}

function updateGrams(idx, val) {
  const v = parseFloat(val)
  customHerbs.value[idx].grams = isNaN(v) ? null : v
}

async function runCustomAnalyze() {
  if (!customCanAnalyze.value) return
  customLoading.value = true
  customError.value = ''
  try {
    customResult.value = (await analyzeCustomRecipe(
      customHerbs.value,
      customClaim.value || null,
    )).data.data
  } catch (e) {
    customError.value = e?.response?.data?.detail || '分析失败，请检查网络后重试'
  } finally { customLoading.value = false }
}

const customClaim = ref('')

// 证据等级：根据数据情况给出综合评级
function evidenceLevel(r) {
  // 有临床文献 → A；有靶点/疾病统计显著 → B；只有传统功效 → C
  const hasClinical = r.herbs?.some(h =>
    h.targets?.some(t => parseFloat(t.p_value) < 0.001))
  const hasTargets = (r.all_targets?.length || 0) > 0
  if (hasClinical) return 'A'
  if (hasTargets) return 'B'
  return 'C'
}
const evidenceLabel = { A: '临床证据支持', B: '实验数据支持', C: '传统应用记载' }

// 结果里只要出现 AI 译文，就必须带上 AI 内容声明
const hasAiText = computed(() =>
  customResult.value?.herbs?.some(h => h.functions_cn_source === 'ai') ?? false)
</script>

<template>
  <div class="page">
    <div class="card head-card">
      <h2 class="p-title"><ShoppingBasket :size="18" /> 我的茶罐</h2>
      <p class="p-sub">勾选手边有的食材，看看今晚就能煮什么——反向配伍，附成分证据</p>
    </div>

    <!-- Tab 切换 -->
    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'own' }" @click="activeTab = 'own'">我的茶罐</button>
      <button class="tab-btn" :class="{ active: activeTab === 'custom' }" @click="activeTab = 'custom'">
        自定义鉴方 <span class="tab-new">新</span>
      </button>
    </div>

    <!-- Tab 1：我的茶罐（原有功能） -->
    <template v-if="activeTab === 'own'">
      <van-empty v-if="error && !materials.length" image="error" :description="error" />

      <!-- 已选 -->
      <div class="section-title">已选 {{ selected.size }} 味</div>
      <div class="card">
        <div v-if="selected.size" class="chip-wrap">
          <button v-for="n in shown.sel" :key="n" class="tag sel-tag" @click="toggle(n)">
            {{ n }} <span class="x">✕</span>
          </button>
        </div>
        <p v-else class="hint">从下面勾选你手边有的食材（会记住你的茶罐）</p>
        <button class="btn" style="margin-top: 10px; width: 100%" :disabled="!selected.size || loading"
                @click="runMatch">{{ loading ? '配伍中…' : '找能煮的方子' }}</button>
      </div>

      <!-- 食材选择 -->
      <div class="section-title">勾选食材</div>
      <div class="card">
        <van-search v-model="search" placeholder="搜食材，如：陈皮" class="search-box" />
        <div class="chip-wrap">
          <button v-for="m in shown.pool" :key="m.name" class="tag opt-tag" @click="toggle(m.name)">
            <img :src="matImg(m.name)" alt="" loading="lazy" @error="e => e.target.style.display = 'none'" />
            {{ m.name }}
          </button>
        </div>
        <p v-if="!shown.pool.length" class="hint">没有更多可选食材了</p>
      </div>

      <template v-if="result">
        <!-- 直接能煮 -->
        <div class="section-title">直接能煮（{{ result.suggestions.length }}）</div>
        <div v-if="result.suggestions.length" class="pantry-list">
          <router-link v-for="r in result.suggestions" :key="r.id" :to="`/recipes/${r.id}`"
                       class="card p-item pressable">
            <div class="pi-left">
              <img :src="matImg(r.hit[0] || '')" alt="" loading="lazy" @error="e => e.target.style.visibility = 'hidden'" />
              <Check :size="16" class="pi-check" />
            </div>
            <div class="pi-main">
              <b>{{ r.name }}</b>
              <p class="pi-one">{{ r.oneliner }}</p>
              <div class="pi-tags">
                <span v-for="s in r.scenes.slice(0, 2)" :key="s" class="tag">{{ s }}</span>
                <span v-if="r.hi_blood_count" class="tag lab">高入血成分 ×{{ r.hi_blood_count }}</span>
              </div>
            </div>
          </router-link>
        </div>
        <van-empty v-else image="search" description="现有食材还不能完整煮任何方子，看看下面「差一点」的" />

        <!-- 差一点 -->
        <div v-if="result.partial.length" class="section-title">差一味就齐（{{ result.partial.length }}）</div>
        <div v-if="result.partial.length" class="pantry-list">
          <router-link v-for="r in result.partial" :key="r.id" :to="`/recipes/${r.id}`"
                       class="card p-item partial pressable">
            <div class="pi-left">
              <img :src="matImg(r.hit[0] || '')" alt="" loading="lazy" @error="e => e.target.style.visibility = 'hidden'" />
            </div>
            <div class="pi-main">
              <div class="pi-top">
                <b>{{ r.name }}</b>
                <span class="cov">{{ coverBar(r.coverage) }}%</span>
              </div>
              <p class="pi-miss">还差：<b>{{ r.missing.join('、') }}</b></p>
              <div class="pi-tags">
                <span v-for="s in r.scenes.slice(0, 2)" :key="s" class="tag">{{ s }}</span>
              </div>
            </div>
          </router-link>
        </div>
      </template>
    </template>

    <!-- Tab 2：自定义鉴方 -->
    <template v-else>
      <div class="card custom-intro">
        <div class="ci-icon"><Sparkles :size="18" /></div>
        <div class="ci-text">
          <b>把网上看到的方子输进来，看看靠不靠谱</b>
          <span>从 HERB 数据库查成分/靶点/功效，每味药说清楚管什么的</span>
        </div>
      </div>

      <!-- 添加药材 -->
      <div class="section-title">输入方子（{{ customHerbs.length }} 味）</div>
      <div class="card">
        <div class="add-row">
          <input v-model="customInput" class="add-input" placeholder="输入药材名，如：金银花"
                 @keyup.enter="addCustomHerb" />
          <button class="btn" :disabled="!customInput.trim()" @click="addCustomHerb">添加</button>
        </div>
        <p class="hint" style="margin-top: 8px">
          提示：逐味添加，支持中药名和食材名。数据来自 HERB 数据库（herb.ac.cn）
        </p>

        <!-- 已添加的药材列表 -->
        <div v-if="customHerbs.length" class="custom-list">
          <div v-for="(h, i) in customHerbs" :key="i" class="custom-row">
            <span class="cr-name">{{ h.name }}</span>
            <div class="cr-grams">
              <input type="number" min="0" step="0.5" placeholder="克重（选填）"
                     :value="h.grams ?? ''" @input="e => updateGrams(i, e.target.value)" />
              <span class="cr-unit">g</span>
            </div>
            <button class="cr-del" @click="removeCustomHerb(i)">✕</button>
          </div>
        </div>

        <button class="btn block" style="margin-top: 14px;"
                :disabled="!customCanAnalyze || customLoading"
                @click="runCustomAnalyze">
          {{ customLoading ? '分析中…' : '分析这个方子' }}
        </button>
      </div>

      <!-- 分析结果 -->
      <template v-if="customResult">
        <!-- 一句话结论 -->
        <div class="card cr-summary">
          <div class="crs-top">
            <span class="crs-badge" :class="'lv-' + evidenceLevel(customResult)">
              证据等级 · {{ evidenceLabel[evidenceLevel(customResult)] }}
            </span>
          </div>
          <p class="crs-text">
            这个方子的 <b>{{ customResult.matched_count }}</b> 味药材中，
            有 <b>{{ customResult.matched_count }}</b> 味在 HERB 数据库有记录
            <template v-if="customResult.not_found.length">
              ，<b class="miss">{{ customResult.not_found.length }}</b> 味未找到（{{ customResult.not_found.join('、') }}）
            </template>
            。
          </p>
          <p class="crs-note">以下分析基于成分和靶点的统计富集结果，为体外/文献层面，不等同于人体内功效。</p>
        </div>

        <!-- 逐味药材说人话（主视觉） -->
        <div class="section-title">每味药管什么</div>
        <div class="herb-cards">
          <div v-for="h in customResult.herbs" :key="h.herb_name" class="card herb-card">
            <div class="hc-head">
              <b class="hc-name">{{ h.name_cn || h.herb_name }}</b>
              <span v-if="h.pinyin" class="hc-py">{{ h.pinyin }}</span>
            </div>
            <div v-if="h.properties_cn || h.meridians_cn || h.properties || h.meridians" class="hc-prop">
              <span v-if="h.properties_cn || h.properties">性味：{{ h.properties_cn || h.properties }}</span>
              <span v-if="h.meridians_cn || h.meridians">归经：{{ h.meridians_cn || h.meridians }}</span>
            </div>
            <div v-if="h.functions_cn || h.function_en" class="hc-func">
              <span class="hc-label">
                传统功效<small v-if="h.functions_cn && h.functions_cn_source === 'ai'" class="src-tag">AI 译</small>
              </span>
              <p>{{ h.functions_cn || h.function_en }}</p>
            </div>
            <div v-if="h.indication_en" class="hc-indic">
              <span class="hc-label">主治<small class="src-tag">英译</small></span>
              <p>{{ h.indication_en }}</p>
            </div>
            <div class="hc-stats">
              <span>{{ h.ingredient_count }} 个成分</span>
              <span>{{ h.target_count }} 个靶点</span>
            </div>
          </div>
        </div>

        <!-- 成分 & 靶点（折叠展开） -->
        <div class="section-title">成分与靶点</div>
        <div class="card cr-extra">
          <p class="hint">
            合并 {{ customResult.all_ingredients.length }} 个成分 · {{ customResult.all_targets.length }} 个靶点
            （去重后）。出现药材越多的成分/靶点，越可能是这个方子的共同作用通路。
          </p>

          <div class="cr-section">
            <b>高频成分 Top 10</b>
            <div class="chip-wrap">
              <span v-for="ing in customResult.all_ingredients.slice(0, 10)" :key="ing.name"
                    class="tag ing-tag" :class="{ multi: ing.herb_count >= 2 }">
                {{ ing.name }} <small>×{{ ing.herb_count }}</small>
              </span>
            </div>
          </div>

          <div class="cr-section">
            <b>高频靶点 Top 10</b>
            <div class="chip-wrap">
              <span v-for="t in customResult.all_targets.slice(0, 10)" :key="t.name"
                    class="tag tgt-tag" :class="{ multi: t.herb_count >= 2 }">
                {{ t.name }} <small>×{{ t.herb_count }}</small>
              </span>
            </div>
          </div>
        </div>

        <DisclaimerBanner variant="compound" size="lg" />
        <DisclaimerBanner v-if="hasAiText" variant="ai" />
      </template>

      <p v-if="customError" class="submit-error shake">{{ customError }}</p>
    </template>

    <DisclaimerBanner v-if="activeTab === 'own'" variant="pantry" style="margin-top: 16px;" />
  </div>
</template>

<style scoped>
.head-card { text-align: center; padding: 20px 16px; }
.p-title { font-size: 18px; display: flex; align-items: center; justify-content: center; gap: 6px; color: var(--green-text); }
.p-sub { font-size: 12px; color: var(--ink-400); margin-top: 6px; }
.search-box { padding: 0 0 10px; background: transparent; }
.chip-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
.sel-tag { background: var(--green-700); color: #fff; border-color: var(--green-700); cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.sel-tag .x { opacity: .85; font-size: 10px; }
.opt-tag { cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.opt-tag img { width: 16px; height: 16px; border-radius: 50%; object-fit: cover; }
.hint { font-size: 12px; color: var(--ink-400); }

/* Tab 切换 */
.tab-bar { display: flex; gap: 0; margin: 0 0 14px; background: var(--card); border-radius: 12px; padding: 4px; }
.tab-btn {
  flex: 1; padding: 10px 0; border: none; background: transparent;
  font-size: 13.5px; font-weight: 500; color: var(--ink-500); cursor: pointer;
  border-radius: 9px; transition: all var(--dur-fast) ease; font-family: inherit;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.tab-btn.active { background: var(--green-700); color: #fff; font-weight: 600; }
.tab-new {
  display: inline-block; font-size: 10px; padding: 1px 5px;
  background: var(--amber-500); color: #fff; border-radius: 8px; line-height: 1.4;
}

/* 自定义鉴方介绍卡 */
.custom-intro { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 14px; }
.ci-icon {
  width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0;
  background: var(--green-50); border: 1px solid var(--green-100);
  display: flex; align-items: center; justify-content: center; color: var(--green-text);
}
.ci-text { flex: 1; min-width: 0; }
.ci-text b { display: block; font-size: 14px; color: var(--ink-900); margin-bottom: 3px; }
.ci-text span { font-size: 12px; color: var(--ink-500); line-height: 1.5; }

/* 添加行 */
.add-row { display: flex; gap: 8px; }
.add-input {
  flex: 1; padding: 10px 12px; border: 1px solid var(--green-100); border-radius: 10px;
  font-size: 14px; font-family: inherit; background: var(--card); color: var(--ink-900);
  outline: none; transition: border-color var(--dur-fast);
}
.add-input:focus { border-color: var(--green-600); }

/* 自定义药材列表 */
.custom-list { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.custom-row {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  background: var(--green-50); border-radius: 8px; border: 1px solid var(--green-100);
}
.cr-name { flex: 1; font-size: 14px; font-weight: 600; color: var(--ink-900); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cr-grams { display: flex; align-items: center; gap: 4px; }
.cr-grams input {
  width: 72px; padding: 6px 8px; border: 1px solid var(--green-100);
  border-radius: 6px; font-size: 12.5px; font-family: inherit; background: #fff; text-align: right;
}
.cr-unit { font-size: 12px; color: var(--ink-400); }
.cr-del {
  width: 24px; height: 24px; border-radius: 50%; border: none; background: transparent;
  color: var(--ink-400); cursor: pointer; font-size: 14px; line-height: 1;
}
.cr-del:hover { color: var(--red-text); background: var(--red-50); }

/* 分析结果 */
.cr-summary { border-left: 4px solid var(--green-600); padding: 14px 16px; }
.crs-badge {
  display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;
  background: var(--green-700); color: #fff; margin-bottom: 10px;
}
.crs-badge.lv-A { background: #1d6b4c; }
.crs-badge.lv-B { background: var(--green-700); }
.crs-badge.lv-C { background: var(--amber-600); }
.crs-text { font-size: 14px; color: var(--ink-800); line-height: 1.7; margin: 0 0 6px; }
.crs-text .miss { color: var(--amber-text); }
.crs-note { font-size: 12px; color: var(--ink-400); margin: 0; }

/* 药材卡片 */
.herb-cards { display: grid; grid-template-columns: 1fr; gap: 10px; }
@media (min-width: 540px) { .herb-cards { grid-template-columns: 1fr 1fr; } }
.herb-card { padding: 14px; }
.hc-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.hc-name { font-size: 16px; color: var(--ink-900); font-family: var(--font-serif); }
.hc-py { font-size: 11.5px; color: var(--ink-400); text-transform: capitalize; }
.hc-prop { font-size: 12px; color: var(--ink-500); display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.hc-label { font-size: 11px; color: var(--green-text); font-weight: 600; display: block; margin-bottom: 3px; }
.hc-label .src-tag {
  display: inline-block; margin-left: 5px; padding: 0 5px; border-radius: 6px;
  font-size: 9.5px; font-weight: 500; line-height: 1.6;
  background: var(--amber-500); color: #fff; vertical-align: middle;
}
.hc-func, .hc-indic { margin: 6px 0; }
.hc-func p, .hc-indic p {
  font-size: 13px; color: var(--ink-700); line-height: 1.6; margin: 0;
  font-style: italic; opacity: .9;
}
.hc-stats {
  display: flex; gap: 12px; margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed var(--green-100); font-size: 12px; color: var(--ink-400);
}

/* 成分靶点折叠区 */
.cr-extra { padding: 14px; }
.cr-section { margin-top: 12px; }
.cr-section > b { display: block; font-size: 13px; color: var(--ink-700); margin-bottom: 8px; }
.ing-tag, .tgt-tag {
  font-size: 11.5px; background: var(--green-50); border-color: var(--green-100);
}
.ing-tag.multi, .tgt-tag.multi {
  background: var(--green-700); color: #fff; border-color: var(--green-700);
}
.ing-tag small, .tgt-tag small { opacity: .85; font-weight: 600; }

.pantry-list { display: flex; flex-direction: column; gap: 10px; }
.p-item { display: flex; gap: 12px; padding: 12px; text-decoration: none; color: inherit; position: relative; }
.pi-left { position: relative; width: 56px; height: 56px; border-radius: 12px; overflow: hidden; flex-shrink: 0;
           background: linear-gradient(135deg, var(--green-600), var(--green-900)); }
.pi-left img { width: 100%; height: 100%; object-fit: cover; }
.pi-check { position: absolute; right: 2px; bottom: 2px; color: #fff; background: var(--green-600);
            border-radius: 50%; padding: 2px; }
.p-item.partial { opacity: .92; }
.pi-main { flex: 1; min-width: 0; }
.pi-main b { font-size: 15px; }
.pi-top { display: flex; justify-content: space-between; align-items: center; }
.cov { font-size: 12px; font-weight: 700; color: var(--amber-text); }
.pi-one { font-size: 12px; color: var(--ink-600); margin: 3px 0 6px; }
.pi-miss { font-size: 12px; color: var(--ink-600); margin: 3px 0 6px; }
.pi-miss b { color: var(--amber-text); font-weight: 600; }
.pi-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag.lab { background: var(--green-700); color: #fff; border-color: var(--green-700); }
</style>
