<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import {
  ShoppingBasket, Sparkles, Search, Check, Camera, ImagePlus,
  X, Trash2, ChevronDown, ChevronUp, Plus, ArrowDown,
} from '@lucide/vue'
import {
  getPantryMaterials, pantryMatch, matImg,
  analyzeCustomRecipe, parseCustomRecipeText, getCustomPlain, webLookupHerb, parseRecipeImage,
} from '../api'
import DisclaimerBanner from '../components/DisclaimerBanner.vue'
import PlainCard from '../components/PlainCard.vue'
import ProModeToggle from '../components/ProModeToggle.vue'
import { proMode } from '../utils/proMode'

const activeTab = ref('own')  // 'own' = 我的茶罐 / 'custom' = 自定义鉴方
const materials = ref([])       // 全部可选食材 [{name, count}]
const selected = ref(new Set()) // 勾选的食材名
const search = ref('')
const activeCat = ref('hot')    // 当前分类抽屉：hot | all | flower | root | grain | fresh | sweet
const shelfExpanded = ref(false)
const trayExpanded = ref(false)
const imgFailed = ref({})

const result = ref(null)
const loading = ref(false)
const error = ref('')
const resultsAnchor = ref(null)

const STORE_KEY = 'shiyang_pantry_v1'
const MOBILE_PAGE_SIZE = 24
const TRAY_COLLAPSE_LIMIT = 9

// 家常异名检索映射（与后端 pantry_service._ALIAS 对齐，搜俗名也能命中库内标准名）
const SEARCH_ALIASES = {
  枣: ['红枣', '大枣', '干枣'],
  龙眼肉: ['桂圆', '桂圆肉'],
  薏苡仁: ['薏米', '米仁'],
  山药: ['淮山', '怀山药'],
  枸杞子: ['枸杞', '红枸杞'],
  铁皮石斛: ['石斛', '枫斗'],
  菊花: ['杭白菊', '胎菊', '贡菊'],
  猪瘦肉: ['猪肉', '瘦肉'],
  猪骨: ['筒骨', '大骨'],
  粳米: ['大米', '白米'],
  赤小豆: ['红小豆'],
  马蹄: ['荸荠'],
  余甘子: ['油柑'],
}

// 精确语义归类词表 + 词根兜底（后续继续扩充百味药材也能自动归入对应抽屉，不丢项）
const EXACT_CAT = {
  // 花叶果茶
  陈皮: 'flower', 菊花: 'flower', 决明子: 'flower', 乌梅: 'flower', 荷叶: 'flower',
  金银花: 'flower', 胖大海: 'flower', 桑椹: 'flower', 薄荷: 'flower', 玫瑰花: 'flower',
  覆盆子: 'flower', 桑叶: 'flower', 佛手: 'flower', 山楂: 'flower', 罗汉果: 'flower',
  栀子: 'flower', 淡竹叶: 'flower', 紫苏: 'flower', 槐花: 'flower', 槐米: 'flower',
  代代花: 'flower', 白扁豆花: 'flower', 橘红: 'flower', 化橘红: 'flower', 香橼: 'flower',
  // 根茎本草
  百合: 'root', 麦冬: 'root', 茯苓: 'root', 黄芪: 'root', 铁皮石斛: 'root',
  西洋参: 'root', 甘草: 'root', 桔梗: 'root', 山药: 'root', 鲜芦根: 'root',
  当归: 'root', 黄精: 'root', 肉桂: 'root', 玉竹: 'root', 天冬: 'root',
  地黄: 'root', 党参: 'root', 天麻: 'root', 白芷: 'root', 葛根: 'root',
  灵芝: 'root', 姜黄: 'root', 杜仲叶: 'root', 肉苁蓉: 'root', 昆布: 'root',
  // 谷豆果仁
  枣: 'grain', 莲子: 'grain', 枸杞子: 'grain', 龙眼肉: 'grain', 薏苡仁: 'grain',
  芡实: 'grain', 蜜枣: 'grain', 粳米: 'grain', 酸枣仁: 'grain', 赤小豆: 'grain',
  花生: 'grain', 绿豆: 'grain', 黑芝麻: 'grain', 麦芽: 'grain', 红豆: 'grain',
  眉豆: 'grain', 核桃: 'grain', 板栗: 'grain', 小米: 'grain', 白扁豆: 'grain',
  杏仁: 'grain', 桃仁: 'grain', 火麻仁: 'grain', 砂仁: 'grain', 莱菔子: 'grain',
  紫苏籽: 'grain', 淡豆豉: 'grain', 白果: 'grain', 刀豆: 'grain',
  // 生鲜煲汤
  生姜: 'fresh', 冬瓜: 'fresh', 鸭肉: 'fresh', 猪瘦肉: 'fresh', 鸡肉: 'fresh',
  银耳: 'fresh', 莲藕: 'fresh', 鸡蛋: 'fresh', 鲫鱼: 'fresh', 鲢鱼头: 'fresh',
  马蹄: 'fresh', 雪梨: 'fresh', 菠菜: 'fresh', 羊肉: 'fresh', 白萝卜: 'fresh',
  玉米须: 'fresh', 猪骨: 'fresh', 猪脊骨: 'fresh', 猪肝: 'fresh', 猪肚: 'fresh',
  海棠果: 'fresh', 椰子: 'fresh', 柚子: 'fresh', 木瓜: 'fresh', 排骨: 'fresh',
  乌鸡: 'fresh', 牡蛎: 'fresh',
  // 糖蜜茶奶
  冰糖: 'sweet', 蜂蜜: 'sweet', 绿茶: 'sweet', 红糖: 'sweet', 白糖: 'sweet', 牛奶: 'sweet',
}

function classifyMaterial(name) {
  if (EXACT_CAT[name]) return EXACT_CAT[name]
  if (/糖|蜜|牛乳|牛奶|红茶|绿茶|乌龙|普洱/.test(name)) return 'sweet'
  if (/肉|鸡|鸭|鹅|鱼|骨|排|肝|肚|蹄|蛋|羊|牛|虾|瓜|梨|藕|萝卜|菜|菇|银耳|木耳|姜|马蹄|椰|柚/.test(name)) return 'fresh'
  if (/花|叶|菊|荷|薄荷|紫苏|梅|楂|椹|罗汉果|胖大海|佛手|皮|橘|柑|桑|茶/.test(name)) return 'flower'
  if (/仁|豆|米|麦|芝麻|核桃|栗|花生|芡|莲|枸杞|枣|桂圆|龙眼|籽|子/.test(name)) return 'grain'
  return 'root'
}

const CAT_DEFS = [
  { key: 'hot', label: '常用高频' },
  { key: 'all', label: '全部' },
  { key: 'flower', label: '花叶果茶' },
  { key: 'root', label: '根茎本草' },
  { key: 'grain', label: '谷豆果仁' },
  { key: 'fresh', label: '生鲜煲汤' },
  { key: 'sweet', label: '糖蜜茶奶' },
]

// 空罐一键体验预设（仅保留库内真实存在的食材）
const QUICK_PRESETS = [
  { label: '润燥护嗓常备', items: ['麦冬', '百合', '菊花', '金银花', '冰糖'] },
  { label: '气血温养茶桌', items: ['陈皮', '枸杞子', '枣', '黄芪', '龙眼肉'] },
  { label: '家常祛湿煲汤', items: ['山药', '茯苓', '薏苡仁', '莲子', '猪瘦肉'] },
]

let matchTimer = null

function clearMatchTimer() {
  if (matchTimer) {
    clearTimeout(matchTimer)
    matchTimer = null
  }
}

function scheduleMatch() {
  clearMatchTimer()
  persist()
  if (!selected.value.size) {
    result.value = null
    return
  }
  matchTimer = setTimeout(() => {
    runMatch()
  }, 240)
}

onMounted(async () => {
  document.addEventListener('pointerdown', onDocPointerDown)
  document.addEventListener('keydown', onDocKeyDown)
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || '[]')
    saved.forEach(n => selected.value.add(n))
  } catch { /* ignore */ }
  try {
    materials.value = (await getPantryMaterials()).data.data.items || []
  } catch { error.value = '食材清单加载失败' }
  if (selected.value.size) runMatch()
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointerDown)
  document.removeEventListener('keydown', onDocKeyDown)
  clearMatchTimer()
  if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
})

// 带分类属性的完整食材列表
const enrichedMaterials = computed(() =>
  materials.value.map((m, idx) => ({
    ...m,
    cat: classifyMaterial(m.name),
    isHot: m.count >= 3 || idx < 28,
    aliases: SEARCH_ALIASES[m.name] || [],
  }))
)

// 每个分类的总数与已选角标数
const categoryTabs = computed(() => {
  const all = enrichedMaterials.value
  return CAT_DEFS.map((c) => {
    const list = c.key === 'all'
      ? all
      : c.key === 'hot'
        ? all.filter(m => m.isHot)
        : all.filter(m => m.cat === c.key)
    const selCount = list.reduce((acc, m) => acc + (selected.value.has(m.name) ? 1 : 0), 0)
    return { ...c, total: list.length, selCount }
  }).filter(c => c.key === 'all' || c.key === 'hot' || c.total > 0)
})

// 搜索词或分类切换时重置折叠态
watch([activeCat, search], () => {
  shelfExpanded.value = false
})

// 当前筛选出的食材池（原位勾选：不把已选食材从列表挖走，彻底消除手机连点跳位）
const filteredPool = computed(() => {
  const kw = search.value.trim().toLowerCase()
  const all = enrichedMaterials.value
  if (kw) {
    return all.filter((m) =>
      m.name.toLowerCase().includes(kw) ||
      m.aliases.some(a => a.toLowerCase().includes(kw))
    )
  }
  if (activeCat.value === 'all') return all
  if (activeCat.value === 'hot') return all.filter(m => m.isHot)
  return all.filter(m => m.cat === activeCat.value)
})

const visiblePool = computed(() => {
  if (search.value.trim() || shelfExpanded.value) return filteredPool.value
  return filteredPool.value.slice(0, MOBILE_PAGE_SIZE)
})

const hiddenCount = computed(() =>
  Math.max(0, filteredPool.value.length - visiblePool.value.length)
)

const selectedList = computed(() => [...selected.value])
const visibleSelected = computed(() =>
  trayExpanded.value ? selectedList.value : selectedList.value.slice(0, TRAY_COLLAPSE_LIMIT)
)

const availablePresets = computed(() => {
  const validSet = new Set(materials.value.map(m => m.name))
  return QUICK_PRESETS
    .map(p => ({ ...p, items: p.items.filter(x => validSet.has(x)) }))
    .filter(p => p.items.length >= 2)
})

function toggle(name) {
  const s = new Set(selected.value)
  s.has(name) ? s.delete(name) : s.add(name)
  selected.value = s
  scheduleMatch()
}

function applyPreset(items) {
  const s = new Set(selected.value)
  items.forEach(n => s.add(n))
  selected.value = s
  scheduleMatch()
}

function clearSelected() {
  selected.value = new Set()
  trayExpanded.value = false
  result.value = null
  persist()
}

function persist() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify([...selected.value]))
  } catch { /* ignore */ }
}

async function runMatch() {
  clearMatchTimer()
  if (!selected.value.size) { result.value = null; return }
  loading.value = true
  error.value = ''
  persist()
  try {
    result.value = (await pantryMatch([...selected.value])).data.data
  } catch { error.value = '匹配失败，请重试' } finally { loading.value = false }
}

function scrollToResults() {
  if (!selected.value.size) return
  if (!result.value && !loading.value) runMatch()
  resultsAnchor.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function onImgError(name) {
  imgFailed.value[name] = true
}

function matchedAliasHint(m) {
  const kw = search.value.trim().toLowerCase()
  if (!kw || m.name.toLowerCase().includes(kw)) return ''
  return m.aliases.find(a => a.toLowerCase().includes(kw)) || ''
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

// ---- 一体化方子识别框（粘贴文字 + 点击「+」上传图片或拍照 + Ctrl+V 贴截图） ----
const albumInput = ref(null)      // 相册/文件选图 <input type=file>（不带 capture）
const cameraInput = ref(null)     // 调起相机拍照 <input type=file capture="environment">
const plusWrapRef = ref(null)     // 「+」菜单包裹层（点击外部自动收起）
const plusMenuOpen = ref(false)
const photoLoading = ref(false)
const photoError = ref('')
const photoInfo = ref(null)       // { status, text, herbs:[], rejected:[], corrections:[] }
const photoPreview = ref('')      // 本地预览 URL（objectURL，用完释放）

function togglePlusMenu() {
  if (photoLoading.value) return
  plusMenuOpen.value = !plusMenuOpen.value
}

function onDocPointerDown(e) {
  if (!plusMenuOpen.value) return
  if (plusWrapRef.value && !plusWrapRef.value.contains(e.target)) {
    plusMenuOpen.value = false
  }
}

function onDocKeyDown(e) {
  if (e.key === 'Escape' && plusMenuOpen.value) {
    plusMenuOpen.value = false
  }
}

function triggerAlbum() {
  plusMenuOpen.value = false
  albumInput.value?.click()
}

function triggerCamera() {
  plusMenuOpen.value = false
  cameraInput.value?.click()
}

function clearPhoto() {
  if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
  photoPreview.value = ''
  photoInfo.value = null
  photoError.value = ''
}

async function processImageFile(file) {
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
    photoInfo.value = (await parseRecipeImage(file)).data.data
    // 识别成功就直接把药材填进去（用户看到原文，可自行删改）
    if (photoInfo.value?.status === 'ok') adoptParsedHerbs(photoInfo.value.herbs)
  } catch (err) {
    // 只透出后端给出的中文提示（4xx 校验类）；5xx/超时一律给人话，避免暴露内部错误
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    photoError.value = (status && status < 500 && typeof detail === 'string' && detail)
      ? detail
      : (err?.code === 'ECONNABORTED'
          ? '识别超时了，图片可能太大或服务繁忙，请稍后重试'
          : '识别失败，请换个角度重拍，或直接在输入框粘贴文字')
  } finally { photoLoading.value = false }
}

function onPhotoPicked(e) {
  const file = e.target.files?.[0]
  e.target.value = ''            // 允许重复选同一张
  if (file) processImageFile(file)
}

function onComposerPaste(e) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const it of items) {
    if (it.kind === 'file' && it.type.startsWith('image/')) {
      const file = it.getAsFile()
      if (file) {
        e.preventDefault()
        processImageFile(file)
        return
      }
    }
  }
}

function onComposerDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (file && file.type.startsWith('image/')) {
    processImageFile(file)
  }
}

// 把识别出的药材并进输入列表（同名只补克重，不重复添加）
function adoptParsedHerbs(herbs) {
  for (const h of herbs || []) {
    const exist = customHerbs.value.find(x => x.name === h.name)
    if (exist) {
      if (h.grams != null && exist.grams == null) exist.grams = h.grams
    } else {
      customHerbs.value.push({ name: h.name, grams: h.grams ?? null })
    }
  }
}

// 识别结果为空时给针对性引导
const emptyPhotoHint = computed(() => {
  const st = photoInfo.value?.status
  if (st === 'no_text') {
    return '这张图里没找到文字。请让方子占满画面、光线均匀、别反光或手抖，再拍一次；'
      + '也可以直接在上方对话框里粘贴药材文字。'
  }
  if (st === 'no_herbs') {
    return '认到了文字，但里面没有能核实的药材名。请对照原文看看是不是识别错了，'
      + '或直接在对话框输入正确写法。'
  }
  return ''
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
  <div class="page pantry-page">
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

    <!-- ==================== Tab 1：我的茶罐 ==================== -->
    <template v-if="activeTab === 'own'">
      <van-empty v-if="error && !materials.length" image="error" :description="error" />

      <!-- 顶部茶罐托盘：空罐给一键组合示例，入罐后紧凑展示并实时汇总可煮数 -->
      <div class="card tray-card">
        <div class="tray-head">
          <div class="tray-title">
            <span class="tray-dot" :class="{ on: selected.size > 0 }" />
            <b>已入罐 {{ selected.size }} 味</b>
            <span v-if="loading" class="tray-status">正在配伍…</span>
            <button
              v-else-if="result && selected.size"
              type="button"
              class="tray-jump pressable"
              @click="scrollToResults"
            >
              直接能煮 {{ result.suggestions.length }} · 差一味 {{ result.partial.length }}
              <ArrowDown :size="11" />
            </button>
          </div>
          <button v-if="selected.size" type="button" class="tray-clear pressable" @click="clearSelected">
            <Trash2 :size="12" /> 清空
          </button>
        </div>

        <!-- 已选食材胶囊（超出阈值自动折叠，避免手机端把下方货架顶出屏幕） -->
        <template v-if="selected.size">
          <div class="chip-wrap tray-chips">
            <button
              v-for="n in visibleSelected"
              :key="n"
              type="button"
              class="tag sel-tag pressable"
              @click="toggle(n)"
            >
              <span>{{ n }}</span>
              <X :size="12" :stroke-width="2.2" class="sel-x" />
            </button>
            <button
              v-if="selectedList.length > TRAY_COLLAPSE_LIMIT"
              type="button"
              class="tag more-sel-btn pressable"
              @click="trayExpanded = !trayExpanded"
            >
              {{ trayExpanded ? '收起' : `全部 ${selectedList.length} 味` }}
            </button>
          </div>
        </template>

        <!-- 空罐引导：省掉原来的大块无效灰按钮，改为一键填入常备茶桌示例 -->
        <div v-else class="tray-empty">
          <p class="hint">点选下方任意药材/食材即可自动配伍（自动记住你的茶罐），或一键试试常备组合：</p>
          <div v-if="availablePresets.length" class="preset-row">
            <button
              v-for="p in availablePresets"
              :key="p.label"
              type="button"
              class="preset-pill pressable"
              @click="applyPreset(p.items)"
            >
              <Plus :size="12" :stroke-width="2.2" />
              <span>{{ p.label }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 分类本草货架：搜索 + 横向滑动分屉 + 原位三列点选网格 -->
      <div class="section-head-row">
        <div class="section-title" style="margin: 0;">勾选食材</div>
        <span v-if="materials.length" class="shelf-meta">
          共收录 {{ materials.length }} 味配料
        </span>
      </div>

      <div class="card shelf-card">
        <!-- 搜索框：支持红枣/桂圆/薏米/淮山等家常俗名自动匹配 -->
        <div class="shelf-search">
          <Search :size="15" class="shelf-search-ico" />
          <input
            v-model="search"
            type="search"
            class="shelf-search-input"
            placeholder="搜药材或家常名，如：陈皮 / 红枣 / 桂圆 / 薏米"
          />
          <button v-if="search" type="button" class="shelf-search-clear" @click="search = ''" aria-label="清空搜索">
            <X :size="14" />
          </button>
        </div>

        <!-- 横向滑动分类抽屉（搜索时提示跨全库检索，平时按分屉快速定位） -->
        <div v-if="!search.trim()" class="cat-rail" role="tablist" aria-label="食材分类">
          <button
            v-for="c in categoryTabs"
            :key="c.key"
            type="button"
            role="tab"
            :aria-selected="activeCat === c.key"
            class="cat-pill pressable"
            :class="{ active: activeCat === c.key }"
            @click="activeCat = c.key"
          >
            <span>{{ c.label }}</span>
            <span v-if="c.selCount" class="cat-sel-badge">{{ c.selCount }}</span>
            <span v-else class="cat-total">{{ c.total }}</span>
          </button>
        </div>
        <div v-else class="search-stat-bar">
          <span>全库检索到 <b>{{ filteredPool.length }}</b> 味相关食材</span>
          <button type="button" class="link-reset" @click="search = ''">返回分类浏览</button>
        </div>

        <!-- 原位三列紧凑卡片网格：点击不跳位、大触控热区、带入方频次参考 -->
        <div v-if="visiblePool.length" class="mat-grid">
          <button
            v-for="m in visiblePool"
            :key="m.name"
            type="button"
            class="mat-tile pressable"
            :class="{ checked: selected.has(m.name) }"
            :aria-pressed="selected.has(m.name)"
            @click="toggle(m.name)"
          >
            <span class="mt-thumb">
              <img
                v-if="!imgFailed[m.name]"
                :src="matImg(m.name)"
                alt=""
                loading="lazy"
                @error="onImgError(m.name)"
              />
              <span v-else class="mt-fallback">{{ m.name.slice(0, 1) }}</span>
            </span>
            <span class="mt-body">
              <span class="mt-name">{{ m.name }}</span>
              <span class="mt-sub">
                <template v-if="matchedAliasHint(m)">俗称{{ matchedAliasHint(m) }}</template>
                <template v-else>入 {{ m.count }} 方</template>
              </span>
            </span>
            <span v-if="selected.has(m.name)" class="mt-check" aria-hidden="true">
              <Check :size="11" :stroke-width="2.8" />
            </span>
          </button>
        </div>

        <p v-else class="hint empty-pool-hint">
          没在配料架里找到「{{ search.trim() }}」，可换个常见别名，或切到上方「自定义鉴方」直接查单味本草。
        </p>

        <!-- 移动端友好的折叠/展开控制：避免一次铺开上百味食材淹没下方结果 -->
        <button
          v-if="!search.trim() && (hiddenCount > 0 || (shelfExpanded && filteredPool.length > MOBILE_PAGE_SIZE))"
          type="button"
          class="shelf-more-btn pressable"
          @click="shelfExpanded = !shelfExpanded"
        >
          <template v-if="!shelfExpanded">
            <span>展开其余 {{ hiddenCount }} 味食材（本组共 {{ filteredPool.length }} 味）</span>
            <ChevronDown :size="14" />
          </template>
          <template v-else>
            <span>收起部分食材，方便浏览下方结果</span>
            <ChevronUp :size="14" />
          </template>
        </button>
      </div>

      <!-- 配伍结果锚点区 -->
      <div ref="resultsAnchor" class="results-anchor">
        <template v-if="result && selected.size">
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
          <van-empty v-else image="search" description="现有食材还不能凑齐整道方子，看看下面「差一味就齐」的" />

          <!-- 差一点：支持在卡片上直接补勾手边其实也有的那味配料 -->
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
                <div class="pi-miss-row">
                  <span class="pi-miss-label">还差：</span>
                  <button
                    v-for="ms in r.missing"
                    :key="ms"
                    type="button"
                    class="miss-add-chip pressable"
                    title="手边也有这味？点一下直接补入茶罐"
                    @click.stop.prevent="toggle(ms)"
                  >
                    <Plus :size="10" :stroke-width="2.4" />
                    <span>{{ ms }}</span>
                  </button>
                </div>
                <div class="pi-tags">
                  <span v-for="s in r.scenes.slice(0, 2)" :key="s" class="tag">{{ s }}</span>
                </div>
              </div>
            </router-link>
          </div>
        </template>
      </div>

      <!-- 手机端悬浮茶罐底栏：浏览长列表勾选时随时感知匹配进度并一键直达结果 -->
      <Transition name="dock-pop">
        <div v-if="selected.size > 0" class="pantry-dock">
          <div class="pd-info">
            <span class="pd-badge">{{ selected.size }}</span>
            <div class="pd-text">
              <b>已选 {{ selected.size }} 味食材</b>
              <span v-if="loading">正在计算可煮方子…</span>
              <span v-else-if="result">
                直接能煮 <em>{{ result.suggestions.length }}</em> 道 · 差一点 <em>{{ result.partial.length }}</em> 道
              </span>
            </div>
          </div>
          <button type="button" class="btn pd-btn pressable" :disabled="loading" @click="scrollToResults">
            <span>看可煮方子</span>
            <ArrowDown :size="14" :stroke-width="2.2" />
          </button>
        </div>
      </Transition>
    </template>

    <!-- ==================== Tab 2：自定义鉴方 ==================== -->
    <template v-else>
      <div class="card custom-intro">
        <div class="ci-icon"><Sparkles :size="18" /></div>
        <div class="ci-text">
          <b>把网上看到的方子输进来，看看靠不靠谱</b>
          <span>从 HERB 数据库查成分/靶点/功效，每味药说清楚管什么的</span>
        </div>
      </div>

      <!-- 一体化方子录入对话框（支持粘贴文案 + 点「+」上传图片或拍照识别 + Ctrl+V 贴截图） -->
      <div class="section-title">智能识别方子</div>
      <div class="card composer-card">
        <input ref="albumInput" type="file" accept="image/jpeg,image/jpg,image/png,image/webp"
               class="photo-input" @change="onPhotoPicked" />
        <input ref="cameraInput" type="file" accept="image/jpeg,image/jpg,image/png,image/webp"
               capture="environment" class="photo-input" @change="onPhotoPicked" />

        <div class="composer-shell">
          <!-- 图片附件内嵌预览条 -->
          <div v-if="photoPreview" class="comp-attachment">
            <img :src="photoPreview" alt="待识别的方子图片" class="comp-thumb" />
            <div class="comp-att-body">
              <span v-if="photoLoading" class="comp-att-status is-loading">
                <span class="att-spin" aria-hidden="true"></span>
                <span>正在识别图中方子文字…</span>
              </span>
              <span v-else-if="photoInfo?.status === 'ok'" class="comp-att-status is-ok">
                <Check :size="13" :stroke-width="2.6" />
                <span>已从图片识别 <b>{{ photoInfo.herbs.length }}</b> 味药材，已填入下方列表</span>
              </span>
              <span v-else-if="photoError" class="comp-att-status is-err">{{ photoError }}</span>
              <span v-else-if="photoInfo" class="comp-att-status">{{ emptyPhotoHint }}</span>
            </div>
            <button v-if="!photoLoading" type="button" class="comp-att-clear pressable"
                    aria-label="移除图片" title="移除图片" @click="clearPhoto">
              <X :size="14" :stroke-width="2.2" />
            </button>
          </div>

          <textarea
            v-model="pasteText"
            class="comp-textarea"
            rows="3"
            maxlength="2000"
            placeholder="把网上看到的方子整段粘进来，如：「金银花10g、菊花5g、枸杞8克，煮水代茶饮」；也可点左下角「+」上传图片或拍照识方"
            @paste="onComposerPaste"
            @drop.prevent="onComposerDrop"
            @dragover.prevent
          ></textarea>

          <!-- 对话框底栏：左下角「+」呼出上传图片/拍照菜单，右下角自动提取药材 -->
          <div class="comp-toolbar">
            <div ref="plusWrapRef" class="comp-plus-wrap">
              <button
                type="button"
                class="comp-plus-btn pressable"
                :class="{ open: plusMenuOpen }"
                :disabled="photoLoading"
                :aria-expanded="plusMenuOpen"
                aria-haspopup="menu"
                aria-label="上传图片或拍照识别方子"
                @click="togglePlusMenu"
              >
                <Plus :size="18" :stroke-width="2.3" class="comp-plus-ico" />
              </button>
              <button
                type="button"
                class="comp-plus-tip"
                :disabled="photoLoading"
                @click="togglePlusMenu"
              >
                {{ photoLoading ? '识别图片中…' : '传图 / 拍照' }}
              </button>

              <Transition name="plus-pop">
                <div v-if="plusMenuOpen" class="comp-plus-menu" role="menu">
                  <button type="button" class="comp-menu-item pressable" role="menuitem" @click="triggerAlbum">
                    <span class="cmi-ico"><ImagePlus :size="17" :stroke-width="2" /></span>
                    <span class="cmi-txt">
                      <b>上传图片</b>
                      <small>从相册选择方子截图或照片</small>
                    </span>
                  </button>
                  <button type="button" class="comp-menu-item pressable" role="menuitem" @click="triggerCamera">
                    <span class="cmi-ico"><Camera :size="17" :stroke-width="2" /></span>
                    <span class="cmi-txt">
                      <b>拍照识方</b>
                      <small>打开相机拍摄药方或处方笺</small>
                    </span>
                  </button>
                </div>
              </Transition>
            </div>

            <div class="comp-actions">
              <span class="comp-verify-hint">AI 抽取 · 逐条核对数据源</span>
              <button
                type="button"
                class="btn comp-extract-btn"
                :disabled="!pasteText.trim() || pasteLoading || photoLoading"
                @click="parsePaste"
              >
                <Sparkles :size="14" :stroke-width="2.2" />
                {{ pasteLoading ? '解析中…' : '自动提取药材' }}
              </button>
            </div>
          </div>
        </div>

        <p v-if="photoError && !photoPreview" class="submit-error shake">{{ photoError }}</p>

        <!-- 图片识别详情：原文核对 + 形近字自动纠错提示 + 未采用条目 -->
        <div v-if="photoInfo" class="photo-result">
          <template v-if="photoInfo.status === 'ok'">
            <div class="ocr-box">
              <span class="ocr-label">图片原文（请核对）</span>
              <pre class="ocr-text">{{ photoInfo.text }}</pre>
            </div>
            <div v-if="photoInfo.corrections?.length" class="pf-fix" style="margin-top: 8px;">
              <b>已自动纠正 {{ photoInfo.corrections.length }} 处疑似识别错误：</b>
              <ul>
                <li v-for="(c, i) in photoInfo.corrections" :key="i">
                  {{ c.from }} <span class="fix-arrow">→</span> {{ c.to }}
                </li>
              </ul>
              <div class="hint" style="margin-top: 4px;">如与原文不符，请在下方列表里改回来</div>
            </div>
            <div v-if="photoInfo.rejected?.length" class="pf-rej" style="margin-top: 8px;">
              <b>未采用的条目：</b>
              <ul>
                <li v-for="(r, i) in photoInfo.rejected" :key="i">
                  {{ r.name }} —— {{ r.reason }}
                </li>
              </ul>
            </div>
          </template>
          <template v-else-if="photoInfo.text">
            <div class="ocr-box">
              <span class="ocr-label">图片原文（供你参考）</span>
              <pre class="ocr-text">{{ photoInfo.text }}</pre>
            </div>
          </template>
        </div>

        <!-- 文本解析结果反馈 -->
        <div v-if="pasteInfo" class="paste-feedback">
          <p v-if="pasteInfo.herbs.length" class="pf-ok">
            已提取 <b>{{ pasteInfo.herbs.length }}</b> 味药材并填入下方列表
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
            <button type="button" class="cr-del" aria-label="移除该药材" @click="removeCustomHerb(i)">
              <X :size="14" :stroke-width="2" />
            </button>
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
.pantry-page { padding-bottom: 24px; }
.head-card { text-align: center; padding: 18px 16px; }
.p-title { font-size: 18px; display: flex; align-items: center; justify-content: center; gap: 6px; color: var(--green-text); }
.p-sub { font-size: 12px; color: var(--ink-400); margin-top: 5px; line-height: 1.5; }
.chip-wrap { display: flex; flex-wrap: wrap; gap: 7px; }
.hint { font-size: 12px; color: var(--ink-400); line-height: 1.55; }
.cta-bar { margin-top: 14px; display: flex; justify-content: center; }
.cta-btn { width: 100%; }
@media (min-width: 540px) {
  .cta-bar { justify-content: flex-start; }
  .cta-btn { width: auto; min-width: 196px; padding: 10px 26px; }
}

/* Tab 切换：暖凹槽 + 纸白浮卡 */
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

/* ============ 顶部「已入罐」紧凑托盘 ============ */
.tray-card {
  padding: 12px 14px;
  margin-bottom: 14px;
}
.tray-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.tray-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  font-size: 13.5px;
  color: var(--ink-900);
}
.tray-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(120, 95, 60, 0.25);
  transition: background var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.tray-dot.on {
  background: var(--green-600);
  box-shadow: 0 0 0 3px rgba(58, 122, 94, 0.14);
}
.tray-status {
  font-size: 11.5px;
  color: var(--ink-400);
}
.tray-jump {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--green-100);
  background: var(--green-50);
  color: var(--green-text);
  font-size: 11.5px;
  font-weight: 600;
  font-family: inherit;
  padding: 2px 9px;
  border-radius: 999px;
  cursor: pointer;
}
.tray-jump:hover {
  border-color: var(--green-600);
  background: var(--green-100);
}
.tray-clear {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: transparent;
  color: var(--ink-400);
  font-size: 12px;
  font-family: inherit;
  padding: 3px 6px;
  border-radius: 6px;
  cursor: pointer;
  transition: color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.tray-clear:hover {
  color: var(--red-text);
  background: var(--red-50);
}

.tray-chips {
  margin-top: 10px;
}
.sel-tag {
  background: var(--green-50); color: var(--green-text);
  border: 1px solid rgba(58, 122, 94, 0.28); border-radius: 999px;
  padding: 4px 9px 4px 11px; font-size: 12.5px; font-weight: 500;
  cursor: pointer; display: inline-flex; align-items: center; gap: 4px; margin: 0;
  font-family: inherit;
}
.sel-tag:hover { background: var(--green-100); border-color: var(--green-600); }
.sel-x { opacity: .65; transition: opacity var(--dur-fast) ease, color var(--dur-fast) ease; }
.sel-tag:hover .sel-x { opacity: 1; color: var(--red-text); }
.more-sel-btn {
  background: transparent;
  border: 1px dashed var(--card-border);
  color: var(--ink-600);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
}

.tray-empty {
  margin-top: 8px;
}
.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 8px;
}
.preset-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 11px;
  border-radius: 999px;
  border: 1px dashed rgba(58, 122, 94, 0.34);
  background: var(--green-50);
  color: var(--green-text);
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.preset-pill:hover {
  border-style: solid;
  border-color: var(--green-600);
  background: var(--green-100);
}

/* ============ 分类食材货架（移动端优先） ============ */
.section-head-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 4px 0 8px;
}
.shelf-meta {
  font-size: 11.5px;
  color: var(--ink-400);
}
.shelf-card {
  padding: 12px;
}

/* 自研轻量搜索条：比 Vant 默认灰框更贴合宣纸卡片且零多余边距 */
.shelf-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 11px;
  border-radius: 10px;
  background: rgba(120, 95, 60, 0.055);
  border: 1px solid rgba(120, 95, 60, 0.12);
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.shelf-search:focus-within {
  border-color: var(--green-600);
  background: var(--card);
}
.shelf-search-ico {
  flex-shrink: 0;
  color: var(--ink-400);
}
.shelf-search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13.5px;
  font-family: inherit;
  color: var(--ink-900);
}
.shelf-search-input::placeholder {
  color: var(--ink-400);
}
.shelf-search-clear {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: rgba(120, 95, 60, 0.12);
  color: var(--ink-600);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

/* 横向滑动分屉栏：手机单手左右滑，隐藏滚动条 */
.cat-rail {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  margin: 10px -2px 11px;
  padding: 2px 2px 3px;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}
.cat-rail::-webkit-scrollbar { display: none; }
.cat-pill {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  border-radius: 999px;
  border: 1px solid var(--card-border);
  background: transparent;
  color: var(--ink-600);
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  transition: all var(--dur-fast) ease;
}
.cat-pill:hover:not(.active) {
  border-color: rgba(58, 122, 94, 0.35);
  color: var(--ink-900);
}
.cat-pill.active {
  background: var(--green-700);
  border-color: var(--green-700);
  color: #fdfaf1;
  font-weight: 600;
}
.cat-total {
  font-size: 10.5px;
  opacity: 0.65;
  font-variant-numeric: tabular-nums;
}
.cat-sel-badge {
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: var(--green-600);
  color: #fdfaf1;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.cat-pill.active .cat-sel-badge {
  background: #fdfaf1;
  color: var(--green-700);
}

.search-stat-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 9px 2px 10px;
  font-size: 12px;
  color: var(--ink-600);
}
.link-reset {
  border: none;
  background: none;
  color: var(--green-text);
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
}

/* 原位紧凑三列网格（手机 3 列整齐对位，平板/桌面自适应 4~6 列） */
.mat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 7px;
}
@media (max-width: 350px) {
  .mat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (min-width: 560px) {
  .mat-grid { grid-template-columns: repeat(auto-fill, minmax(132px, 1fr)); gap: 8px; }
}

.mat-tile {
  position: relative;
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 44px;
  padding: 6px 8px 6px 6px;
  border-radius: 10px;
  border: 1px solid var(--card-border);
  background: rgba(120, 95, 60, 0.025);
  color: var(--ink-900);
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.mat-tile:hover {
  border-color: rgba(58, 122, 94, 0.38);
  background: var(--green-50);
}
.mat-tile.checked {
  border-color: var(--green-600);
  background: var(--green-50);
  box-shadow: inset 0 0 0 1px rgba(58, 122, 94, 0.18);
}

.mt-thumb {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--green-100);
  display: flex;
  align-items: center;
  justify-content: center;
}
.mt-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.mt-fallback {
  font-size: 12px;
  font-weight: 700;
  font-family: var(--font-serif);
  color: var(--green-text);
}

.mt-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.mt-name {
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1.25;
  color: var(--ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mat-tile.checked .mt-name {
  color: var(--green-text);
}
.mt-sub {
  font-size: 10px;
  line-height: 1.2;
  color: var(--ink-400);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mt-check {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  background: var(--green-700);
  color: #fdfaf1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 4px rgba(20, 51, 42, 0.25);
}

.empty-pool-hint {
  padding: 18px 8px;
  text-align: center;
}

.shelf-more-btn {
  width: 100%;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 9px;
  border: 1px dashed var(--card-border);
  background: rgba(120, 95, 60, 0.035);
  color: var(--ink-600);
  font-size: 12.5px;
  font-family: inherit;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  cursor: pointer;
  transition: border-color var(--dur-fast) ease, color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.shelf-more-btn:hover {
  border-color: var(--green-600);
  color: var(--green-text);
  background: var(--green-50);
}

.results-anchor {
  scroll-margin-top: 68px;
  margin-top: 14px;
}

/* 差一味卡片上的快捷补入胶囊 */
.pi-miss-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  margin: 4px 0 6px;
}
.pi-miss-label {
  font-size: 12px;
  color: var(--ink-600);
}
.miss-add-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px dashed rgba(176, 124, 46, 0.45);
  background: var(--amber-50);
  color: var(--amber-text);
  font-size: 11.5px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}
.miss-add-chip:hover {
  border-style: solid;
  border-color: var(--green-600);
  background: var(--green-50);
  color: var(--green-text);
}

/* ============ 手机端悬浮茶罐结果底栏 ============ */
.pantry-dock {
  position: sticky;
  bottom: calc(12px + var(--tabbar-offset, 0px));
  z-index: 18;
  margin-top: 14px;
  padding: 9px 11px 9px 13px;
  border-radius: 999px;
  background: var(--card);
  border: 1px solid rgba(58, 122, 94, 0.30);
  box-shadow: var(--shadow-hover);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.pd-info {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}
.pd-badge {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--green-700);
  color: #fdfaf1;
  font-size: 12.5px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-variant-numeric: tabular-nums;
}
.pd-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.pd-text b {
  font-size: 12.5px;
  color: var(--ink-900);
  line-height: 1.25;
}
.pd-text span {
  font-size: 11px;
  color: var(--ink-600);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pd-text em {
  font-style: normal;
  font-weight: 700;
  color: var(--green-text);
}
.pd-btn {
  flex-shrink: 0;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 12.5px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dock-pop-enter-active,
.dock-pop-leave-active {
  transition: opacity 0.22s ease, transform 0.22s var(--ease-out-soft);
}
.dock-pop-enter-from,
.dock-pop-leave-to {
  opacity: 0;
  transform: translateY(10px);
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

/* 一体化智能方子录入框（文字粘贴 + 「+」上传图片/拍照识方） */
.photo-input { display: none; }
.composer-card { padding: 14px; }
.composer-shell {
  border: 1px solid var(--green-100);
  border-radius: 12px;
  background: var(--card);
  box-shadow: inset 0 1px 2px rgba(74, 56, 32, 0.04);
  transition: border-color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.composer-shell:focus-within {
  border-color: var(--green-600);
  box-shadow: 0 0 0 3px rgba(58, 122, 94, 0.10);
}

/* 对话框内嵌图片预览条 */
.comp-attachment {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 10px 10px 0;
  padding: 8px 10px;
  border-radius: 9px;
  background: var(--green-50);
  border: 1px solid rgba(58, 122, 94, 0.18);
}
.comp-thumb {
  width: 48px;
  height: 48px;
  border-radius: 7px;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid var(--card-border);
  background: var(--card);
}
.comp-att-body {
  flex: 1;
  min-width: 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-600);
}
.comp-att-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.comp-att-status.is-loading { color: var(--green-text); font-weight: 500; }
.comp-att-status.is-ok { color: var(--green-text); }
.comp-att-status.is-err { color: var(--red-text); }
.att-spin {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid rgba(58, 122, 94, 0.24);
  border-top-color: var(--green-700);
  animation: spin 0.75s linear infinite;
  flex-shrink: 0;
}
.comp-att-clear {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: rgba(120, 95, 60, 0.08);
  color: var(--ink-600);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background var(--dur-fast) ease, color var(--dur-fast) ease;
}
.comp-att-clear:hover {
  background: var(--red-50);
  color: var(--red-text);
}

.comp-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 13px 8px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.65;
  color: var(--ink-900);
  resize: vertical;
  min-height: 84px;
  outline: none;
}
.comp-textarea::placeholder {
  color: var(--ink-400);
}

/* 对话框底栏 */
.comp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 10px 9px;
  border-top: 1px dashed rgba(120, 95, 60, 0.14);
}
.comp-plus-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.comp-plus-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid rgba(58, 122, 94, 0.30);
  background: var(--green-50);
  color: var(--green-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease, color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.comp-plus-btn:hover:not(:disabled) {
  background: var(--green-100);
  border-color: var(--green-600);
}
.comp-plus-btn.open {
  background: var(--green-700);
  border-color: var(--green-700);
  color: #fdfaf1;
  box-shadow: 0 2px 8px rgba(42, 95, 74, 0.26);
}
.comp-plus-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.comp-plus-ico {
  transition: transform 0.22s var(--ease-snap);
}
.comp-plus-btn.open .comp-plus-ico {
  transform: rotate(45deg);
}
.comp-plus-tip {
  border: none;
  background: none;
  padding: 4px 2px;
  font-family: inherit;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--ink-600);
  cursor: pointer;
  white-space: nowrap;
}
.comp-plus-tip:hover:not(:disabled) {
  color: var(--green-text);
}
.comp-plus-tip:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* 「+」弹出菜单：上传图片 / 拍照识方 */
.comp-plus-menu {
  position: absolute;
  left: 0;
  bottom: calc(100% + 9px);
  z-index: 35;
  width: 226px;
  padding: 6px;
  border-radius: 12px;
  background: var(--card);
  border: 1px solid var(--card-border);
  box-shadow: 0 10px 28px -6px rgba(42, 56, 48, 0.22), 0 2px 6px rgba(42, 56, 48, 0.08);
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.comp-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: none;
  border-radius: 9px;
  background: transparent;
  text-align: left;
  font-family: inherit;
  cursor: pointer;
  transition: background var(--dur-fast) ease;
}
.comp-menu-item:hover {
  background: var(--green-50);
}
.cmi-ico {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--green-50);
  border: 1px solid var(--green-100);
  color: var(--green-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.comp-menu-item:hover .cmi-ico {
  background: var(--card);
  border-color: rgba(58, 122, 94, 0.32);
}
.cmi-txt {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.cmi-txt b {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink-900);
  line-height: 1.3;
}
.cmi-txt small {
  font-size: 11px;
  color: var(--ink-400);
  line-height: 1.35;
  margin-top: 1px;
}

.plus-pop-enter-active,
.plus-pop-leave-active {
  transition: opacity 0.16s ease, transform 0.18s var(--ease-snap);
  transform-origin: bottom left;
}
.plus-pop-enter-from,
.plus-pop-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.95);
}

.comp-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.comp-verify-hint {
  font-size: 11.5px;
  color: var(--ink-400);
  white-space: nowrap;
}
.comp-extract-btn {
  padding: 8px 15px;
  font-size: 13px;
  border-radius: 999px;
  white-space: nowrap;
}
@media (max-width: 520px) {
  .comp-verify-hint { display: none; }
  .comp-toolbar { padding: 6px 8px 8px; }
}

.photo-result { margin-top: 10px; font-size: 12.5px; line-height: 1.6; }
/* 识别出的原文：等宽、可复制、限高滚动，方便用户对照核对 */
.ocr-box {
  margin-top: 8px; padding: 10px 12px; border-radius: 9px;
  background: var(--green-50); border: 1px solid rgba(58, 122, 94, 0.18);
}
.ocr-label {
  display: block; font-size: 10.5px; font-weight: 600;
  color: var(--green-text); margin-bottom: 5px;
}
.ocr-text {
  margin: 0; font-size: 12.5px; line-height: 1.75; color: var(--ink-700);
  font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
  white-space: pre-wrap; word-break: break-word;
  max-height: 190px; overflow-y: auto;
}

.paste-feedback { margin-top: 10px; font-size: 12.5px; line-height: 1.6; }
.pf-ok { color: var(--green-text); margin: 0 0 6px; }
.pf-none { color: var(--ink-600); margin: 0 0 6px; }
.pf-rej { background: var(--amber-50); border: 1px solid rgba(176, 124, 46, 0.28); border-radius: 8px; padding: 8px 10px; }
.pf-rej b { display: block; color: var(--amber-text); margin-bottom: 4px; }
.pf-rej ul { margin: 0; padding-left: 16px; color: var(--ink-600); }
.pf-rej li { margin-bottom: 2px; }
.submit-error { margin-top: 10px; padding: 9px 12px; background: var(--red-50); border: 1px solid rgba(176, 74, 58, 0.24); color: var(--red-text); border-radius: 9px; font-size: 13px; line-height: 1.55; }

/* OCR 形近字纠正提示（蓝调，区别于"未采用"的琥珀色警告） */
.pf-fix { background: var(--green-50); border: 1px solid rgba(58, 122, 94, 0.22); border-radius: 8px; padding: 8px 10px; }
.pf-fix b { display: block; color: var(--green-text); margin-bottom: 4px; }
.pf-fix ul { margin: 0; padding-left: 16px; color: var(--ink-600); }
.pf-fix li { margin-bottom: 2px; }
.fix-arrow { color: var(--green-700); font-weight: 700; margin: 0 2px; }

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
  border-radius: 6px; font-size: 12.5px; font-family: inherit; background: var(--card); color: var(--ink-900); text-align: right;
}
.cr-unit { font-size: 12px; color: var(--ink-400); }
.cr-del {
  width: 24px; height: 24px; border-radius: 50%; border: none; background: transparent;
  color: var(--ink-400); cursor: pointer; display: inline-flex; align-items: center; justify-content: center;
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
.cr-section > b { display: block; font-size: 13px; color: var(--ink-900); margin-bottom: 8px; }
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
.p-item.partial { opacity: .95; }
.pi-main { flex: 1; min-width: 0; }
.pi-main b { font-size: 15px; }
.pi-top { display: flex; justify-content: space-between; align-items: center; }
.cov { font-size: 12px; font-weight: 700; color: var(--amber-text); }
.pi-one { font-size: 12px; color: var(--ink-600); margin: 3px 0 6px; }
.pi-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag.lab { background: var(--green-700); color: #fff; border-color: var(--green-700); }

/* 联网搜索兜底卡片 */
.wl-spin { font-size: 11.5px; font-weight: 400; color: var(--ink-400); margin-left: 6px; }
.wl-list { display: flex; flex-direction: column; gap: 10px; }
.wl-card { padding: 13px 14px; border-left: 3px solid var(--amber-600); }
.wl-head { display: flex; align-items: center; gap: 7px; margin-bottom: 7px; color: var(--ink-900); }
.wl-badge {
  font-size: 9.5px; padding: 1px 6px; border-radius: 6px; line-height: 1.6;
  background: var(--amber-600); color: #fff; font-weight: 500;
}
.wl-summary { font-size: 13px; color: var(--ink-600); line-height: 1.7; margin: 0 0 8px; }
.wl-none { font-size: 12.5px; color: var(--ink-400); margin: 0 0 6px; }
.wl-sources { display: flex; flex-direction: column; gap: 3px; }
.wl-src-label { font-size: 11px; color: var(--ink-400); font-weight: 600; }
.wl-src {
  font-size: 12px; color: var(--green-text); text-decoration: none;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.wl-src:hover { text-decoration: underline; }
</style>
