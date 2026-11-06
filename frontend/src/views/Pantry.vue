<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ShoppingBasket, Sparkles, Search, Check, Camera } from '@lucide/vue'
import { showSuccessToast } from 'vant'
import { getPantryMaterials, pantryMatch, matImg, analyzeCustomRecipe, parseCustomRecipeText, getCustomPlain, webLookupHerb, recognizeRecipeImage } from '../api'
import DisclaimerBanner from '../components/DisclaimerBanner.vue'
import PlainCard from '../components/PlainCard.vue'
import ProModeToggle from '../components/ProModeToggle.vue'
import { proMode } from '../utils/proMode'

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
// 「说人话」解读：分析结果出来后再请求 AI 改写，失败不影响主结果
const customPlain = ref(null)
const customPlainLoading = ref(false)
const customPlainError = ref('')

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
    runCustomPlain()
  } catch (e) {
    customError.value = e?.response?.data?.detail || '分析失败，请检查网络后重试'
  } finally { customLoading.value = false }
}

async function runCustomPlain() {
  customPlain.value = null
  customPlainError.value = ''
  // 只送数据库里查到的药材及其传统资料；未找到的不送，避免模型凭空编作用
  const herbs = (customResult.value?.herbs || []).map(h => ({
    name: h.name_cn || h.herb_name,
    grams: h.grams ?? null,
    properties: String(h.properties_cn || h.properties || '') || null,
    functions: String(h.functions_cn || h.function_en || '') || null,
  }))
  if (!herbs.length) return
  customPlainLoading.value = true
  try {
    customPlain.value = (await getCustomPlain(herbs)).data.data
  } catch {
    customPlainError.value = '白话解读暂时没生成出来，可以先看下方每味药的传统功效。'
  } finally { customPlainLoading.value = false }
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

// ---- 拍照识药 ----
const photoInput = ref(null)      // <input type=file> 引用
const photoLoading = ref(false)
const photoError = ref('')
const photoInfo = ref(null)       // { image_kind, items:[], unverified:[] }
const photoPreview = ref('')      // 本地预览 URL（objectURL，用完释放）

function triggerPhoto() {
  photoInput.value?.click()
}

async function onPhotoPicked(e) {
  const file = e.target.files?.[0]
  e.target.value = ''            // 允许重复选同一张
  if (!file) return
  // 前端先拦一道，省一次失败的请求
  if (!/^image\/(jpeg|jpg|png|webp)$/i.test(file.type)) {
    photoError.value = '请上传 JPG / PNG / WEBP 格式的图片'
    return
  }
  if (file.size > 8 * 1024 * 1024) {
    photoError.value = '图片超过 8MB，请在相册里压缩后再传'
    return
  }
  if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
  photoPreview.value = URL.createObjectURL(file)
  photoLoading.value = true
  photoError.value = ''
  photoInfo.value = null
  try {
    photoInfo.value = (await recognizeRecipeImage(file)).data.data
  } catch (err) {
    // 只透出后端给出的中文提示（4xx 校验类）；5xx/超时一律给人话，避免暴露内部错误
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    photoError.value = (status && status < 500 && typeof detail === 'string' && detail)
      ? detail
      : (err?.code === 'ECONNABORTED'
          ? '识别超时了，图片可能太大或服务繁忙，请稍后重试'
          : '识别失败，请换个角度重拍或改用手动输入')
  } finally { photoLoading.value = false }
}

// 点选某个候选 → 填入药材列表（同类药材多候选时让用户自己判断）
function pickRecognized(item) {
  const name = item.name_cn || item.name
  const exist = customHerbs.value.find(x => x.name === name)
  if (exist) {
    if (item.grams != null && exist.grams == null) exist.grams = item.grams
  } else {
    customHerbs.value.push({ name, grams: item.grams ?? null })
  }
  // 已选的候选从建议里移除，避免重复点
  photoInfo.value.items = photoInfo.value.items.filter(i => i !== item)
}

// 一键采纳所有已入库的候选
function pickAllRecognized() {
  const verified = (photoInfo.value?.items || []).filter(i => i.verified)
  for (const it of [...verified]) pickRecognized(it)
}

// 识别不出时按图片类型给不同引导（验收反馈：原来一句话覆盖不了多种失败原因）
const emptyPhotoHint = computed(() => {
  const kind = photoInfo.value?.image_kind
  if (kind === 'text') {
    return '图片里的文字没看清。请让药方占满画面、光线均匀、别反光或手抖，再拍一次。'
  }
  if (kind === 'herb') {
    return '认不出是什么。粉末、切片、碎末很难辨认；药材请平铺在一块干净的背景上、'
      + '距离 20–30 厘米、光线充足后重拍。也可以改用手动输入。'
  }
  return '这张图里没发现能识别的药材或药方。请拍药材实物（散开平铺）或药方文字，'
    + '确保画面清晰、不模糊、不逆光。'
})

// ---- 粘贴文案自动解析 ----
const pasteText = ref('')
const pasteLoading = ref(false)
const pasteError = ref('')
const pasteInfo = ref(null)   // { herbs: [...], rejected: [...] }

async function parsePaste() {
  const t = pasteText.value.trim()
  if (!t) return
  pasteLoading.value = true
  pasteError.value = ''
  pasteInfo.value = null
  try {
    pasteInfo.value = (await parseCustomRecipeText(t)).data.data
    // 抽到的药材直接并进输入列表（去重，克重保留）
    for (const h of pasteInfo.value.herbs) {
      const exist = customHerbs.value.find(x => x.name === h.name)
      if (exist) {
        if (h.grams != null && exist.grams == null) exist.grams = h.grams
      } else {
        customHerbs.value.push({ name: h.name, grams: h.grams ?? null })
      }
    }
    if (pasteInfo.value.herbs.length) pasteText.value = ''
  } catch (e) {
    pasteError.value = e?.response?.data?.detail || '解析失败，请稍后重试'
  } finally { pasteLoading.value = false }
}

// 结果里只要出现 AI 译文，就必须带上 AI 内容声明
const hasAiText = computed(() =>
  customResult.value?.herbs?.some(h => h.functions_cn_source === 'ai') ?? false)

// ---- 联网搜索兜底（HERB 查不到的药材/奇怪输入 → 搜「有什么作用」+ 真实来源） ----
const webLookups = ref({})   // {药名: {status, summary_cn, sources, ...}}
const webLookupLoading = ref(false)

async function runWebLookups(names) {
  if (!names?.length) return
  webLookupLoading.value = true
  // 并发搜，但每味独立 try/catch：一个失败不拖累其他
  await Promise.all(names.map(async n => {
    try {
      webLookups.value = { ...webLookups.value, [n]: (await webLookupHerb(n)).data.data }
    } catch {
      webLookups.value = { ...webLookups.value, [n]: { status: 'error', name: n, summary_cn: null, sources: [] } }
    }
  }))
  webLookupLoading.value = false
}

// 有未找到的药材且尚未查询过 → 自动发起联网兜底
watch(() => customResult.value, r => {
  const missing = (r?.not_found || []).filter(n => !webLookups.value[n])
  if (missing.length) runWebLookups(missing)
})
</script>

<template>
  <div class="page">
    <div class="card head-card">
      <h2 class="p-title"><ShoppingBasket :size="18" /> 我的茶罐</h2>
      <p class="p-sub">勾选手边有的食材，看看今晚就能煮什么——反向配伍，附成分证据</p>
    </div>

    <!-- Tab 切换 -->
    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'own' }" @click="activeTab = 'own'">
        <ShoppingBasket :size="14" /> 我的茶罐
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'custom' }" @click="activeTab = 'custom'">
        <Sparkles :size="14" /> 自定义鉴方 <span class="tab-new">新</span>
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
        <div class="cta-bar">
          <button class="btn cta-btn" :disabled="!selected.size || loading" @click="runMatch">
            <Search :size="15" :stroke-width="2.2" />
            {{ loading ? '配伍中…' : '找能煮的方子' }}
          </button>
        </div>
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

      <!-- 拍照识药 -->
      <div class="section-title">拍照识药（最快）</div>
      <div class="card">
        <input ref="photoInput" type="file" accept="image/jpeg,image/jpg,image/png,image/webp"
               capture="environment" class="photo-input" @change="onPhotoPicked" />
        <div class="photo-row">
          <button class="btn" :disabled="photoLoading" @click="triggerPhoto">
            <Camera :size="15" />{{ photoLoading ? '识别中…' : '拍照 / 选图' }}
          </button>
          <span class="hint">拍药材实物，或拍药方纸条</span>
        </div>

        <div v-if="photoPreview" class="photo-preview-wrap">
          <img :src="photoPreview" alt="待识别的图片" class="photo-preview" />
        </div>

        <p v-if="photoError" class="submit-error shake">{{ photoError }}</p>

        <!-- 识别结果：候选项让用户点选，绝不自动填入 -->
        <div v-if="photoInfo" class="photo-result">
          <p v-if="!photoInfo.items.length" class="pf-none">{{ emptyPhotoHint }}</p>
          <template v-else>
            <p class="pf-ok">
              认出 <b>{{ photoInfo.items.length }}</b> 个可能的药材，点一下加入（可多选）：
            </p>
            <div class="cand-wrap">
              <button v-for="(it, i) in photoInfo.items" :key="i" class="cand"
                      :class="{ unverified: !it.verified }" @click="pickRecognized(it)">
                <span class="cand-name">{{ it.name_cn || it.name }}</span>
                <span v-if="it.grams != null" class="cand-g">{{ it.grams }}g</span>
                <span class="cand-conf">{{ Math.round(it.confidence * 100) }}%</span>
                <span v-if="!it.verified" class="cand-tag">库中无</span>
              </button>
            </div>
            <button v-if="photoInfo.items.some(i => i.verified)" class="btn ghost"
                    style="margin-top: 8px;" @click="pickAllRecognized">
              全部加入（仅已入库的）
            </button>
          </template>
          <div v-if="photoInfo.unverified?.length" class="pf-rej" style="margin-top: 8px;">
            <b>数据库里没有的名字：</b>{{ photoInfo.unverified.join('、') }}
            <div class="hint" style="margin-top: 4px;">可改名后手动输入，或后续查看联网说明</div>
          </div>
        </div>
      </div>

      <!-- 粘贴文案自动解析 -->
      <div class="section-title">或者粘贴方子文案</div>
      <div class="card">
        <textarea v-model="pasteText" class="paste-box" rows="4"
                  placeholder="把网上看到的方子整段粘进来，如：「金银花10g、菊花5g、枸杞8克，煮水代茶饮」"
                  maxlength="2000"></textarea>
        <div class="paste-row">
          <button class="btn" :disabled="!pasteText.trim() || pasteLoading" @click="parsePaste">
            {{ pasteLoading ? '解析中…' : '自动提取药材' }}
          </button>
          <span class="hint">AI 抽取，逐条核对数据源</span>
        </div>

        <!-- 解析结果反馈 -->
        <div v-if="pasteInfo" class="paste-feedback">
          <p v-if="pasteInfo.herbs.length" class="pf-ok">
            已提取 <b>{{ pasteInfo.herbs.length }}</b> 味药材并加入上方列表
          </p>
          <p v-else class="pf-none">这段文案里没有识别到可查证的药材</p>
          <div v-if="pasteInfo.rejected.length" class="pf-rej">
            <b>未采用的条目：</b>
            <ul>
              <li v-for="(r, i) in pasteInfo.rejected" :key="i">
                {{ r.name }} —— {{ r.reason }}
              </li>
            </ul>
          </div>
        </div>
        <p v-if="pasteError" class="submit-error shake">{{ pasteError }}</p>
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

        <div class="cta-bar" style="margin-top: 14px;">
          <button class="btn cta-btn"
                  :disabled="!customCanAnalyze || customLoading"
                  @click="runCustomAnalyze">
            <Sparkles :size="15" :stroke-width="2.2" />
            {{ customLoading ? '分析中…' : '分析这个方子' }}
          </button>
        </div>
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
            这个方子的 <b>{{ customResult.matched_count + customResult.not_found.length }}</b> 味药材中，
            有 <b>{{ customResult.matched_count }}</b> 味在 HERB 数据库有记录
            <template v-if="customResult.not_found.length">
              ，<b class="miss">{{ customResult.not_found.length }}</b> 味未找到（{{ customResult.not_found.join('、') }}）
            </template>
            。
          </p>
          <p class="crs-note">以下分析基于成分和靶点的统计富集结果，为体外/文献层面，不等同于人体内功效。</p>
        </div>

        <!-- 大众层：整方白话解读（AI 生成，组件内带来源标注） -->
        <PlainCard :plain="customPlain" :loading="customPlainLoading" :error="customPlainError"
                   title="用大白话说说这个方子" />

        <!-- 逐味药材说人话（主视觉） -->
        <div class="section-title">每味药管什么</div>
        <div class="herb-cards">
          <div v-for="h in customResult.herbs" :key="h.herb_name" class="card herb-card">
            <div class="hc-head">
              <b class="hc-name">{{ h.name_cn || h.herb_name }}</b>
              <span v-if="h.pinyin" class="hc-py">{{ h.pinyin }}</span>
            </div>
            <div v-if="proMode && (h.properties_cn || h.meridians_cn || h.properties || h.meridians)" class="hc-prop">
              <span v-if="h.properties_cn || h.properties">性味：{{ h.properties_cn || h.properties }}</span>
              <span v-if="h.meridians_cn || h.meridians">归经：{{ h.meridians_cn || h.meridians }}</span>
            </div>
            <div v-if="h.functions_cn || h.function_en" class="hc-func">
              <span class="hc-label">
                传统功效<small v-if="h.functions_cn && h.functions_cn_source === 'ai'" class="src-tag">AI 译</small>
              </span>
              <p>{{ h.functions_cn || h.function_en }}</p>
            </div>
            <div v-if="proMode && h.indication_en" class="hc-indic">
              <span class="hc-label">主治<small class="src-tag">英译</small></span>
              <p>{{ h.indication_en }}</p>
            </div>
            <div v-if="proMode" class="hc-stats">
              <span>{{ h.ingredient_count }} 个成分</span>
              <span>{{ h.target_count }} 个靶点</span>
            </div>
          </div>
        </div>

        <ProModeToggle hint="性味归经、成分与作用靶点等研究数据" style="margin-top: 12px;" />

        <!-- 联网搜索兜底：HERB 未命中的药材，搜「有什么作用」附真实来源 -->
        <template v-if="customResult.not_found.length">
          <div class="section-title">
            数据库没查到的
            <span v-if="webLookupLoading" class="wl-spin">联网查询中…</span>
          </div>
          <div class="wl-list">
            <div v-for="n in customResult.not_found" :key="n" class="card wl-card">
              <div class="wl-head">
                <Search :size="14" />
                <b>{{ n }}</b>
                <span class="wl-badge">AI 联网整理</span>
              </div>
              <template v-if="webLookups[n]">
                <p v-if="webLookups[n].status === 'ok'" class="wl-summary">{{ webLookups[n].summary_cn }}</p>
                <p v-else-if="webLookups[n].status === 'no_result'" class="wl-none">
                  没有搜到可靠来源的介绍，请谨慎对待这个名字——它可能是误写、自创名或极冷门的叫法。
                </p>
                <p v-else class="wl-none">联网查询失败，可稍后重试。</p>
                <div v-if="webLookups[n].sources?.length" class="wl-sources">
                  <span class="wl-src-label">来源（真实搜索结果）：</span>
                  <a v-for="(s, i) in webLookups[n].sources" :key="i" :href="s.url" target="_blank"
                     rel="noopener noreferrer" class="wl-src">{{ s.title || s.url }}</a>
                </div>
              </template>
              <p v-else class="wl-none">正在联网查询这种材料的作用…</p>
            </div>
          </div>
          <DisclaimerBanner variant="ai" />
        </template>

        <!-- 成分 & 靶点（专业层） -->
        <template v-if="proMode">
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
        </template>

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
.chip-wrap { display: flex; flex-wrap: wrap; gap: 7px; }
.sel-tag {
  background: var(--green-50); color: var(--green-text);
  border: 1px solid rgba(58, 122, 94, 0.28); border-radius: 999px;
  padding: 4px 11px; font-size: 12.5px; font-weight: 500;
  cursor: pointer; display: inline-flex; align-items: center; gap: 5px; margin: 0;
}
.sel-tag:hover { background: var(--green-100); border-color: var(--green-600); }
.sel-tag .x { opacity: .65; font-size: 10px; line-height: 1; transition: opacity var(--dur-fast) ease, color var(--dur-fast) ease; }
.sel-tag:hover .x { opacity: 1; color: var(--red-text); }
.opt-tag {
  cursor: pointer; display: inline-flex; align-items: center; gap: 5px;
  border-radius: 999px; padding: 4px 11px 4px 5px; font-size: 12.5px; margin: 0;
}
.opt-tag:hover { border-color: rgba(58, 122, 94, 0.36); background: var(--green-100); }
.opt-tag img { width: 18px; height: 18px; border-radius: 50%; object-fit: cover; }
.hint { font-size: 12px; color: var(--ink-400); }
.cta-bar { margin-top: 14px; display: flex; justify-content: center; }
.cta-btn { width: 100%; }
@media (min-width: 540px) {
  .cta-bar { justify-content: flex-start; }
  .cta-btn { width: auto; min-width: 196px; padding: 10px 26px; }
}

/* Tab 切换：暖凹槽 + 纸白浮卡，避免与下方主操作按钮撞成两块深绿大长条 */
.tab-bar {
  display: flex; gap: 4px; margin: 0 0 14px;
  background: rgba(120, 95, 60, 0.075);
  border: 1px solid var(--card-border);
  border-radius: 12px; padding: 4px;
}
.tab-btn {
  flex: 1; padding: 9px 12px; border: 1px solid transparent; background: transparent;
  font-size: 13.5px; font-weight: 500; color: var(--ink-600); cursor: pointer;
  border-radius: 9px; transition: all var(--dur-fast) ease; font-family: inherit;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.tab-btn:hover:not(.active) { color: var(--ink-900); background: rgba(255, 255, 255, 0.35); }
.tab-btn.active {
  background: var(--card); color: var(--green-text); font-weight: 600;
  border-color: var(--card-border);
  box-shadow: 0 2px 8px -2px rgba(74, 56, 32, 0.12), 0 1px 2px rgba(74, 56, 32, 0.06);
}
.tab-new {
  display: inline-block; font-size: 10px; font-weight: 600; padding: 1px 5px;
  background: var(--cinnabar); color: #fbf3e4; border-radius: 6px; line-height: 1.35;
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
.ci-text span { font-size: 12px; color: var(--ink-600); line-height: 1.5; }

/* 拍照识药 */
.photo-input { display: none; }
.photo-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.photo-preview-wrap { margin-top: 10px; }
.photo-preview {
  max-width: 100%; max-height: 200px; border-radius: 10px;
  border: 1px solid var(--green-100); object-fit: cover;
}
.photo-result { margin-top: 10px; font-size: 12.5px; line-height: 1.6; }
.cand-wrap { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 6px; }
.cand {
  display: inline-flex; align-items: center; gap: 5px; cursor: pointer;
  padding: 6px 11px; border-radius: 999px; margin: 0;
  background: var(--green-50); border: 1px solid rgba(58, 122, 94, 0.28);
  font-size: 13px; color: var(--green-text); font-family: inherit;
  transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease;
}
.cand:hover { background: var(--green-100); border-color: var(--green-600); }
.cand.unverified { background: var(--amber-50); border-color: var(--amber-200); color: var(--amber-text); }
.cand-name { font-weight: 600; }
.cand-g { font-size: 11.5px; opacity: .8; }
.cand-conf { font-size: 10.5px; opacity: .7; }
.cand-tag {
  font-size: 9.5px; padding: 0 5px; border-radius: 5px;
  background: var(--amber-500); color: #fff; line-height: 1.6;
}

/* 粘贴解析 */
.paste-box {  width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 10px;
  border: 1px solid var(--green-100); font-size: 13.5px; font-family: inherit;
  line-height: 1.6; color: var(--ink-900); background: var(--card);
  resize: vertical; outline: none; transition: border-color var(--dur-fast);
}
.paste-box:focus { border-color: var(--green-600); }
.paste-row { display: flex; align-items: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
.paste-feedback { margin-top: 10px; font-size: 12.5px; line-height: 1.6; }
.pf-ok { color: var(--green-text); margin: 0 0 6px; }
.pf-none { color: var(--ink-600); margin: 0 0 6px; }
.pf-rej { background: var(--amber-50); border: 1px solid rgba(176, 124, 46, 0.28); border-radius: 8px; padding: 8px 10px; }
.pf-rej b { display: block; color: var(--amber-text); margin-bottom: 4px; }
.pf-rej ul { margin: 0; padding-left: 16px; color: var(--ink-600); }
.pf-rej li { margin-bottom: 2px; }

/* 添加行 */
.add-row { display: flex; gap: 8px; }.add-input {
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
  border-radius: 6px; font-size: 12.5px; font-family: inherit; background: var(--card); color: var(--ink-900); text-align: right;
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
.crs-text { font-size: 14px; color: var(--ink-900); line-height: 1.7; margin: 0 0 6px; }
.crs-text .miss { color: var(--amber-text); }
.crs-note { font-size: 12px; color: var(--ink-400); margin: 0; }

/* 药材卡片 */
.herb-cards { display: grid; grid-template-columns: 1fr; gap: 10px; }
@media (min-width: 540px) { .herb-cards { grid-template-columns: 1fr 1fr; } }
.herb-card { padding: 14px; }
.hc-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.hc-name { font-size: 16px; color: var(--ink-900); font-family: var(--font-serif); }
.hc-py { font-size: 11.5px; color: var(--ink-400); text-transform: capitalize; }
.hc-prop { font-size: 12px; color: var(--ink-600); display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.hc-label { font-size: 11px; color: var(--green-text); font-weight: 600; display: block; margin-bottom: 3px; }
.hc-label .src-tag {
  display: inline-block; margin-left: 5px; padding: 0 5px; border-radius: 6px;
  font-size: 9.5px; font-weight: 500; line-height: 1.6;
  background: var(--amber-600); color: #fff; vertical-align: middle;
}
.hc-func, .hc-indic { margin: 6px 0; }
.hc-func p, .hc-indic p {
  font-size: 13px; color: var(--ink-600); line-height: 1.6; margin: 0;
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

/* 联网搜索兜底卡片 */
.wl-spin { font-size: 11.5px; font-weight: 400; color: var(--ink-400); margin-left: 6px; }
.wl-list { display: flex; flex-direction: column; gap: 10px; }
.wl-card { padding: 13px 14px; border-left: 3px solid var(--amber-500); }
.wl-head { display: flex; align-items: center; gap: 7px; margin-bottom: 7px; color: var(--ink-700); }
.wl-badge {
  font-size: 9.5px; padding: 1px 6px; border-radius: 6px; line-height: 1.6;
  background: var(--amber-500); color: #fff; font-weight: 500;
}
.wl-summary { font-size: 13px; color: var(--ink-700); line-height: 1.7; margin: 0 0 8px; }
.wl-none { font-size: 12.5px; color: var(--ink-400); margin: 0 0 6px; }
.wl-sources { display: flex; flex-direction: column; gap: 3px; }
.wl-src-label { font-size: 11px; color: var(--ink-400); font-weight: 600; }
.wl-src {
  font-size: 12px; color: var(--green-text); text-decoration: none;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.wl-src:hover { text-decoration: underline; }
</style>
