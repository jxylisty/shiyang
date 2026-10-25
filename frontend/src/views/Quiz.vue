<script setup>
import { ref, computed, onMounted } from 'vue'
import { getQuestionnaire, submitQuiz, saveRecord, isLoggedIn, listFamilyMembers } from '../api'

const items = ref({})          // {code: [题...]}
const order = ref([])          // 维度顺序
const answers = ref({})        // {code: [null|1-5,...]}
const idx = ref(0)             // 当前题号（展平后）
const flat = ref([])           // [{code, q, di}]
const submitting = ref(false)
const result = ref(null)
const error = ref('')
const qDir = ref(1)            // 题目切换方向：1 前进 / -1 后退
const justPicked = ref(null)   // 刚选中的选项值：驱动 pop 弹跳
const revealed = ref(false)    // 结果页揭示：进度条从 0 生长
const shownScores = ref({})    // 九维分数滚动显示值
// 家庭代测（T2-8）：0=本人，>0 为成员 id
const members = ref([])
const forMember = ref(0)
onMounted(async () => {
  if (isLoggedIn()) {
    try { members.value = (await listFamilyMembers()).data.data } catch { /* 静默 */ }
  }
})

const OPTIONS = [
  { label: '没有', v: 1 }, { label: '很少', v: 2 }, { label: '有时', v: 3 },
  { label: '经常', v: 4 }, { label: '总是', v: 5 },
]
const NAME = { pinghe: '平和', qixu: '气虚', yangxu: '阳虚', yinxu: '阴虚', tanshi: '痰湿', shire: '湿热', xueyu: '血瘀', qiyu: '气郁', tebing: '特禀' }

onMounted(async () => {
  try {
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
  } catch {
    error.value = '问卷加载失败，请检查网络后刷新重试'
  }
})
// 每次作答后暂存进度
import { watch } from 'vue'
watch(answers, saveProgress, { deep: true })

const cur = () => flat.value[idx.value]
const answeredCount = () => flat.value.filter(x => answers.value[x.code][x.di] !== null).length

let advanceTimer = null
let pickTimer = null

function buzz(ms) {
  try { navigator.vibrate?.(ms) } catch { /* 不支持则静默 */ }
}

function choose(v) {
  const c = cur()
  if (!c) return
  answers.value[c.code][c.di] = v
  // 选中弹跳 + 轻触觉反馈
  justPicked.value = v
  buzz(8)
  if (pickTimer) clearTimeout(pickTimer)
  pickTimer = setTimeout(() => { justPicked.value = null }, 450)
  // 防双击：先清掉未生效的跳题定时器，且钳制不越界（越界会让 cur() 为 undefined 导致渲染崩溃）
  if (advanceTimer) { clearTimeout(advanceTimer); advanceTimer = null }
  if (idx.value < flat.value.length - 1) {
    advanceTimer = setTimeout(() => {
      advanceTimer = null
      qDir.value = 1
      idx.value = Math.min(idx.value + 1, flat.value.length - 1)
    }, 150)
  }
}

function nextQ() { qDir.value = 1; idx.value = Math.min(idx.value + 1, flat.value.length - 1) }
function prevQ() { qDir.value = -1; idx.value = Math.max(idx.value - 1, 0) }

// 题目卡过渡的 JS 钩子（setTimeout 收尾，隐藏页签不卡死）：
// qDir=1 前进：新卡从右侧滑入；qDir=-1 后退：从左侧滑入
function qEnter(el, done) {
  const dx = qDir.value === 1 ? 28 : -28
  el.style.opacity = '0'
  el.style.transform = `translateX(${dx}px)`
  // rAF 冻结环境下 50ms 内由 setTimeout 兜底起播
  let started = false
  const start = () => {
    if (started) return
    started = true
    el.style.transition = 'opacity .18s ease, transform .2s cubic-bezier(0.22, 1, 0.36, 1)'
    el.style.opacity = '1'
    el.style.transform = 'translateX(0)'
  }
  requestAnimationFrame(start)
  setTimeout(start, 50)
  setTimeout(() => { el.style.transition = ''; el.style.opacity = ''; el.style.transform = ''; done() }, 280)
}
function qLeave(el, done) {
  const dx = qDir.value === 1 ? -20 : 20
  el.style.transition = 'opacity .15s ease, transform .16s cubic-bezier(0.22, 1, 0.36, 1)'
  el.style.opacity = '0'
  el.style.transform = `translateX(${dx}px)`
  setTimeout(done, 180)
}

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
  qDir.value = 1
  result.value = null
  revealed.value = false
  clearProgress()
}

// 九维分数滚动：单条 setTimeout 时间轴同步推所有维度
// （不用 rAF：页面隐藏/截屏场景 rAF 会被暂停，数字永远停在 0）
function animateScores(results) {
  const targets = Object.fromEntries(Object.entries(results).map(([k, v]) => [k, v.score]))
  const dur = 900, t0 = performance.now()
  const tick = () => {
    const p = Math.min(1, (performance.now() - t0) / dur)
    const ease = 1 - Math.pow(1 - p, 3)
    for (const k of Object.keys(targets)) {
      shownScores.value[k] = Math.round(targets[k] * ease)
    }
    if (p < 1) setTimeout(tick, 16)
  }
  tick()
}

async function submit() {
  submitting.value = true; error.value = ''
  try {
    const res = (await submitQuiz(answers.value)).data.data
    result.value = res
    clearProgress()
    // 已登录 → 自动存入体质档案（可挂家庭成员；失败不打断展示）
    if (isLoggedIn()) {
      saveRecord(res.judged, res.transformed, answers.value,
                 forMember.value || null).catch(() => {})
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
    // 揭示动画：setTimeout 下一拍把进度条从 0 播到终值，同时分数滚动
    // （双 setTimeout 替代双 rAF：隐藏页签里 rAF 不触发会导致进度条定格 0）
    setTimeout(() => setTimeout(() => {
      revealed.value = true
      animateScores(res.judged.results)
    }, 16), 16)
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
      <div class="card result-hero pop-card">
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

      <div class="section-title rise" style="--i: 1">九种体质得分</div>
      <div class="card rise" style="--i: 2">
        <div v-for="(v, code) in result.judged.results" :key="code" class="score-row">
          <span class="s-name">{{ NAME[code] }}</span>
          <van-progress class="s-bar" :percentage="revealed ? Math.round(v.score) : 0" color="var(--green-600)" track-color="#d7e8df" :show-pivot="false" />
          <span class="s-val">{{ shownScores[code] ?? 0 }}</span>
          <span class="s-tag" :class="{ hit: v.result !== '否' }">{{ v.result }}</span>
        </div>
      </div>

      <div class="section-title rise" style="--i: 3">为您推荐的方子</div>
      <div class="card rise" style="--i: 4">
        <template v-if="result.recommendations.length">
          <router-link v-for="(r, i) in result.recommendations" :key="r.id" :to="`/recipes/${r.id}`" class="recipe-row pressable">
            <div class="r-name">{{ r.name }} <span class="tag" v-for="c in r.matched_constitutions" :key="c">{{ c }}</span></div>
            <div class="r-one">{{ r.oneliner }}</div>
          </router-link>
        </template>
        <p v-else class="empty" style="padding:12px 0">暂无完全匹配的方子，可到<a href="/recipes" style="color:var(--green-700)">方子库</a>按场景浏览</p>
      </div>

      <div class="card diet-ref rise" style="--i: 5" v-if="result.main_constitution && result.main_constitution.foods_suitable">
        <div class="section-title" style="margin-top:0">食养参考</div>
        <p><b>宜：</b>{{ result.main_constitution.foods_suitable.slice(0, 12).join('、') }}</p>
        <p style="margin-top:6px"><b>忌：</b>{{ result.main_constitution.foods_avoid.slice(0, 8).join('、') }}</p>
        <p style="margin-top:6px"><b>茶饮思路：</b>{{ result.main_constitution.tea_ideas.join('；') }}</p>
      </div>

      <button class="btn ghost block rise" style="--i: 6" @click="restart">重新测评</button>
    </template>

    <!-- 答题页 -->
    <template v-else>
      <van-progress class="progress-line" :percentage="answerPercent" color="#359068" track-color="#eef7f2" :show-pivot="false" />
      <p class="p-count">{{ answeredCount() }} / {{ flat.length || 67 }} 题 · 当前维度：{{ NAME[cur()?.code] || '' }}</p>

      <!-- 问卷加载中骨架 -->
      <div class="card" v-if="!flat.length && !error">
        <div class="skl q-skl-title"></div>
        <div class="q-skl-opts">
          <span class="skl q-skl-opt" v-for="n in 5" :key="n"></span>
        </div>
      </div>

      <p v-if="error && !flat.length" class="submit-error shake">{{ error }}</p>

      <!-- 题目卡：方向感切换（前进左滑入 / 后退右滑入）
           :css="false" + JS 钩子：收尾用 setTimeout，不依赖 transitionend
           （隐藏页签/切后台时该事件可能永不到达，out-in 会卡死整页） -->
      <Transition :name="qDir === 1 ? 'q-fwd' : 'q-back'" mode="out-in"
                  :css="false" @enter="qEnter" @leave="qLeave">
        <div class="card q-card" v-if="flat.length && cur()" :key="idx">
          <p class="q-text">{{ idx + 1 }}. {{ cur().q }}</p>
          <div class="opts">
            <button v-for="o in OPTIONS" :key="o.v" class="opt"
                    :class="{ on: answers[cur().code][cur().di] === o.v, pop: justPicked === o.v }"
                    @click="choose(o.v)">{{ o.label }}</button>
          </div>
        </div>
      </Transition>

      <p v-if="error && flat.length" class="submit-error shake">{{ error }}</p>

      <div class="q-nav">
        <button class="btn ghost" v-if="idx > 0" @click="prevQ">上一题</button>
        <button class="btn" v-if="idx < flat.length - 1" @click="nextQ">下一题</button>
        <button class="btn" v-else :disabled="answeredCount() < flat.length || submitting" @click="submit">
          <span v-if="submitting" class="spinner"></span>
          {{ submitting ? '判定中…' : answeredCount() < flat.length ? `还有 ${flat.length - answeredCount()} 题` : '查看体质结果' }}
        </button>
        <button class="btn ghost" v-if="answeredCount() > 0" @click="restart">清空重答</button>
      </div>
      <p class="q-note">共 {{ flat.length || 67 }} 题，约 3 分钟。进度自动保存在本机，误关页面后重新打开可继续作答。</p>
      <!-- 家庭代测（T2-8）：结果将存入选中成员的档案 -->
      <div class="member-pick" v-if="members.length && !result">
        <span class="mp-label">替谁测评：</span>
        <button class="tag mp-tag" :class="{ active: forMember === 0 }" @click="forMember = 0">本人</button>
        <button v-for="m in members" :key="m.id" class="tag mp-tag"
                :class="{ active: forMember === m.id }" @click="forMember = m.id">{{ m.name }}</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.progress-line { height: 5px; margin-bottom: 6px; }
.progress-line :deep(.van-progress__portion) { border-radius: 3px; transition: width var(--dur-med) var(--ease-out-soft); }
.p-count { font-size: 12px; color: var(--ink-400); margin-bottom: 12px; }

/* 题目卡过渡视觉由 qEnter/qLeave JS 钩子内联驱动 */

.q-text { font-size: 17px; font-weight: 600; min-height: 76px; }
.opts { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 10px; }
.opt {
  border: 1px solid var(--green-100); background: #fff; border-radius: 10px; padding: 12px 0; font-size: 13px; color: var(--ink-600); cursor: pointer;
  transition: background var(--dur-fast) ease, color var(--dur-fast) ease, border-color var(--dur-fast) ease, scale var(--dur-fast) var(--ease-snap);
}
.opt:active { scale: 0.94; }
.opt.on { background: var(--green-700); color: #fff; border-color: var(--green-700); font-weight: 600; }
.opt.pop { animation: pop 0.45s var(--ease-spring); }
.q-nav { display: flex; gap: 10px; margin-top: 14px; }
.submit-error { margin-top: 12px; padding: 10px 12px; background: var(--red-50); color: var(--red-500); border-radius: 10px; font-size: 13px; }
.q-nav .btn { flex: 1; text-align: center; }
.q-note { font-size: 11px; color: var(--ink-400); margin-top: 14px; line-height: 1.5; }
.member-pick { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
.mp-label { font-size: 12px; color: var(--ink-400); }
.mp-tag { cursor: pointer; }
.mp-tag.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }

/* 提交按钮 loading 圈 */
.spinner {
  display: inline-block; width: 12px; height: 12px; margin-right: 6px; vertical-align: -1px;
  border: 2px solid rgba(255,255,255,.4); border-top-color: #fff; border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { rotate: 360deg; } }

/* 问卷加载骨架 */
.q-skl-title { height: 48px; margin: 12px 0 4px; }
.q-skl-opts { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 12px; }
.q-skl-opt { height: 42px; border-radius: 10px; }

/* 结果页揭示 */
.result-hero { text-align: center; padding: 26px 16px; animation: rise .5s var(--ease-out-soft) backwards; }
.result-hero .label { font-size: 12px; color: var(--ink-400); }
.result-hero h2 { font-size: 26px; color: var(--green-700); margin: 6px 0; animation: pop .55s var(--ease-spring) .25s backwards; }
.result-hero .principle { font-size: 13px; color: var(--ink-600); }
.combined { margin-top: 8px; font-size: 12px; color: var(--amber-600); }

.score-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
.s-name { width: 42px; font-size: 13px; color: var(--ink-600); }
.s-bar { flex: 1; }
.s-bar :deep(.van-progress__portion) { transition: width var(--dur-slow) var(--ease-out-soft); }
.s-val { width: 34px; text-align: right; font-size: 12px; color: var(--ink-600); font-variant-numeric: tabular-nums; }
.s-tag { width: 44px; font-size: 11px; color: var(--ink-400); text-align: center; }
.s-tag.hit { color: var(--green-700); font-weight: 600; }

.recipe-row { display: block; padding: 10px 0; border-bottom: 1px solid var(--green-50); text-decoration: none; border-radius: 8px; }
.recipe-row:last-child { border-bottom: none; }
.r-name { font-weight: 600; font-size: 15px; color: var(--ink-900); }
.r-one { font-size: 12px; color: var(--ink-400); margin-top: 2px; }
.diet-ref p { font-size: 13px; color: var(--ink-600); line-height: 1.7; }
</style>
