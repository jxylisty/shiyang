<script setup>
import { ref, computed, onMounted } from 'vue'
import { getQuestionnaire, submitQuiz, saveRecord, isLoggedIn } from '../api'

const items = ref({})          // {code: [题...]}
const order = ref([])          // 维度顺序
const answers = ref({})        // {code: [null|1-5,...]}
const idx = ref(0)             // 当前题号（展平后）
const flat = ref([])           // [{code, q, di}]
const submitting = ref(false)
const result = ref(null)
const error = ref('')

const OPTIONS = [
  { label: '没有', v: 1 }, { label: '很少', v: 2 }, { label: '有时', v: 3 },
  { label: '经常', v: 4 }, { label: '总是', v: 5 },
]
const NAME = { pinghe: '平和', qixu: '气虚', yangxu: '阳虚', yinxu: '阴虚', tanshi: '痰湿', shire: '湿热', xueyu: '血瘀', qiyu: '气郁', tebing: '特禀' }

onMounted(async () => {
  const d = (await getQuestionnaire()).data.data
  items.value = d.items
  const a = {}
  const f = []
  for (const [code, qs] of Object.entries(d.items)) {
    a[code] = Array(qs.length).fill(null)
    qs.forEach((q, i) => f.push({ code, q, di: i }))
  }
  answers.value = a
  flat.value = f
  restoreProgress()
})
// 每次作答后暂存进度
import { watch } from 'vue'
watch(answers, saveProgress, { deep: true })

const cur = () => flat.value[idx.value]
const answeredCount = () => flat.value.filter(x => answers.value[x.code][x.di] !== null).length

let advanceTimer = null

function choose(v) {
  const c = cur()
  if (!c) return
  answers.value[c.code][c.di] = v
  // 防双击：先清掉未生效的跳题定时器，且钳制不越界（越界会让 cur() 为 undefined 导致渲染崩溃）
  if (advanceTimer) { clearTimeout(advanceTimer); advanceTimer = null }
  if (idx.value < flat.value.length - 1) {
    advanceTimer = setTimeout(() => {
      advanceTimer = null
      idx.value = Math.min(idx.value + 1, flat.value.length - 1)
    }, 150)
  }
}

function nextQ() { idx.value = Math.min(idx.value + 1, flat.value.length - 1) }
function prevQ() { idx.value = Math.max(idx.value - 1, 0) }

// ---- 进度本地暂存：误关/崩溃后不丢 67 题的作答 ----
const STORE_KEY = 'shiyang_quiz_v1'
function saveProgress() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify({ answers: answers.value, idx: idx.value }))
  } catch { /* 存储不可用时静默 */ }
}
function clearProgress() {
  try { localStorage.removeItem(STORE_KEY) } catch { /* ignore */ }
}
function restoreProgress() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || 'null')
    if (!saved || !saved.answers) return
    for (const [code, arr] of Object.entries(saved.answers)) {
      if (Array.isArray(arr) && Array.isArray(answers.value[code]) && arr.length === answers.value[code].length) {
        answers.value[code] = arr.map(v => (v >= 1 && v <= 5 ? v : null))
      }
    }
    if (typeof saved.idx === 'number') idx.value = Math.max(0, Math.min(saved.idx, flat.value.length - 1))
  } catch { /* 数据不合法则忽略 */ }
}
function restart() {
  if (advanceTimer) { clearTimeout(advanceTimer); advanceTimer = null }
  for (const code of Object.keys(answers.value)) answers.value[code].fill(null)
  idx.value = 0
  result.value = null
  clearProgress()
}

async function submit() {
  submitting.value = true; error.value = ''
  try {
    const res = (await submitQuiz(answers.value)).data.data
    result.value = res
    clearProgress()
    // 已登录 → 自动存入体质档案（失败不打断展示）
    if (isLoggedIn()) {
      saveRecord(res.judged, res.transformed, answers.value).catch(() => {})
    }
    window.scrollTo({ top: 0 })
  } catch (e) {
    // 提交失败不清进度，用户可重试
    error.value = '提交失败，请检查网络后重试（您的作答已保留）'
  } finally { submitting.value = false }
}

// 答题进度百分比
const answerPercent = computed(() =>
  flat.value.length ? Math.round(answeredCount() / flat.value.length * 100) : 0)

// 主体质名：单偏颇 → 主体质；多兼夹/平和 → 按得分最高的偏颇体质给名字，无则「平和」
const mainName = computed(() => {
  const r = result.value
  if (!r) return ''
  if (r.main_constitution) return r.main_constitution.name
  const biased = r.judged.combined
  if (biased.length) return `${NAME[biased[0]]}质为主（兼夹${biased.length - 1}种）`
  if ((r.judged.results.pinghe?.result ?? '否') !== '否') return '平和质'
  return '多体质兼夹'
})
</script>

<template>
  <div class="page">
    <!-- 结果页 -->
    <template v-if="result">
      <div class="card result-hero">
        <p class="label">您的体质倾向</p>
        <!-- 主体质可能为空（多兼夹），始终从 judged 兜底渲染 -->
        <h2>{{ mainName || '多体质兼夹' }}</h2>
        <p v-if="result.main_constitution" class="principle">{{ result.main_constitution.principle }}</p>
        <p v-else class="principle">同时具有多种偏颇体质倾向，建议以「兼夹调理、温和为要」的思路选择方子，并优先改善得分最高的体质。</p>
        <div v-if="result.judged.combined.length" class="combined">
          偏颇体质：{{ result.judged.combined.map(c => NAME[c] + '质').join('、') }}
        </div>
        <div v-else class="combined">各体质得分均未达偏颇标准，保持平和即为理想状态</div>
      </div>

      <div class="section-title">九种体质得分</div>
      <div class="card">
        <div v-for="(v, code) in result.judged.results" :key="code" class="score-row">
          <span class="s-name">{{ NAME[code] }}</span>
          <van-progress class="s-bar" :percentage="Math.round(v.score)" color="var(--green-600)" track-color="#d7e8df" :show-pivot="false" />
          <span class="s-val">{{ v.score }}</span>
          <span class="s-tag" :class="{ hit: v.result !== '否' }">{{ v.result }}</span>
        </div>
      </div>

      <div class="section-title">为您推荐的方子</div>
      <div class="card">
        <template v-if="result.recommendations.length">
          <router-link v-for="r in result.recommendations" :key="r.id" :to="`/recipes/${r.id}`" class="recipe-row">
            <div class="r-name">{{ r.name }} <span class="tag" v-for="c in r.matched_constitutions" :key="c">{{ c }}</span></div>
            <div class="r-one">{{ r.oneliner }}</div>
          </router-link>
        </template>
        <p v-else class="empty" style="padding:12px 0">暂无完全匹配的方子，可到<a href="/recipes" style="color:var(--green-700)">方子库</a>按场景浏览</p>
      </div>

      <div class="card diet-ref" v-if="result.main_constitution && result.main_constitution.foods_suitable">
        <div class="section-title" style="margin-top:0">食养参考</div>
        <p><b>宜：</b>{{ result.main_constitution.foods_suitable.slice(0, 12).join('、') }}</p>
        <p style="margin-top:6px"><b>忌：</b>{{ result.main_constitution.foods_avoid.slice(0, 8).join('、') }}</p>
        <p style="margin-top:6px"><b>茶饮思路：</b>{{ result.main_constitution.tea_ideas.join('；') }}</p>
      </div>

      <button class="btn ghost block" @click="restart">重新测评</button>
    </template>

    <!-- 答题页 -->
    <template v-else>
      <van-progress class="progress-line" :percentage="answerPercent" color="#359068" track-color="#eef7f2" :show-pivot="false" />
      <p class="p-count">{{ answeredCount() }} / {{ flat.length }} 题 · 当前维度：{{ NAME[cur()?.code] || '' }}</p>

      <div class="card q-card" v-if="flat.length && cur()">
        <p class="q-text">{{ idx + 1 }}. {{ cur().q }}</p>
        <div class="opts">
          <button v-for="o in OPTIONS" :key="o.v" class="opt"
                  :class="{ on: answers[cur().code][cur().di] === o.v }"
                  @click="choose(o.v)">{{ o.label }}</button>
        </div>
      </div>

      <p v-if="error" class="submit-error">{{ error }}</p>

      <div class="q-nav">
        <button class="btn ghost" v-if="idx > 0" @click="prevQ">上一题</button>
        <button class="btn" v-if="idx < flat.length - 1" @click="nextQ">下一题</button>
        <button class="btn" v-else :disabled="answeredCount() < flat.length || submitting" @click="submit">
          {{ submitting ? '判定中…' : answeredCount() < flat.length ? `还有 ${flat.length - answeredCount()} 题` : '查看体质结果' }}
        </button>
        <button class="btn ghost" v-if="answeredCount() > 0" @click="restart">清空重答</button>
      </div>
      <p class="q-note">共 {{ flat.length }} 题，约 3 分钟。进度自动保存在本机，误关页面后重新打开可继续作答。</p>
    </template>
  </div>
</template>

<style scoped>
.progress-line { height: 5px; margin-bottom: 6px; }
.progress-line :deep(.van-progress__portion) { border-radius: 3px; }
.p-count { font-size: 12px; color: var(--ink-400); margin-bottom: 12px; }

.q-text { font-size: 17px; font-weight: 600; min-height: 76px; }
.opts { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 10px; }
.opt { border: 1px solid var(--green-100); background: #fff; border-radius: 10px; padding: 12px 0; font-size: 13px; color: var(--ink-600); cursor: pointer; }
.opt.on { background: var(--green-700); color: #fff; border-color: var(--green-700); font-weight: 600; }
.q-nav { display: flex; gap: 10px; margin-top: 14px; }
.submit-error { margin-top: 12px; padding: 10px 12px; background: var(--red-50); color: var(--red-500); border-radius: 10px; font-size: 13px; }
.q-nav .btn { flex: 1; text-align: center; }
.q-note { font-size: 11px; color: var(--ink-400); margin-top: 14px; line-height: 1.5; }

.result-hero { text-align: center; padding: 26px 16px; }
.result-hero .label { font-size: 12px; color: var(--ink-400); }
.result-hero h2 { font-size: 26px; color: var(--green-700); margin: 6px 0; }
.result-hero .principle { font-size: 13px; color: var(--ink-600); }
.combined { margin-top: 8px; font-size: 12px; color: var(--amber-600); }

.score-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
.s-name { width: 42px; font-size: 13px; color: var(--ink-600); }
.s-bar { flex: 1; }
.s-val { width: 34px; text-align: right; font-size: 12px; color: var(--ink-600); }
.s-tag { width: 44px; font-size: 11px; color: var(--ink-400); text-align: center; }
.s-tag.hit { color: var(--green-700); font-weight: 600; }

.recipe-row { display: block; padding: 10px 0; border-bottom: 1px solid var(--green-50); text-decoration: none; }
.recipe-row:last-child { border-bottom: none; }
.r-name { font-weight: 600; font-size: 15px; color: var(--ink-900); }
.r-one { font-size: 12px; color: var(--ink-400); margin-top: 2px; }
.diet-ref p { font-size: 13px; color: var(--ink-600); line-height: 1.7; }
</style>
