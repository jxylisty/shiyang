<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Info } from '@lucide/vue'
import { showConfirmDialog, showToast } from 'vant'
import { makeNavHooks, tween, afterPaint } from '../utils/motion'
import { getQuestionnaire, submitQuiz, saveRecord, isLoggedIn, listFamilyMembers, saveLocalConstitution, getLocalConstitution } from '../api'
import { recordQuizSnapshot } from '../utils/guestArchive'
import RecipeRow from '../components/RecipeRow.vue'
import AppIcon from '../components/AppIcon.vue'

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
const lastResult = ref(null)   // 上次测评（本地暂存）：答卷页给个回看入口，避免复测像"记录丢了"
const showAnswerSheet = ref(false) // 答题卡抽屉控制

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
const ORDER_KEYS = ['pinghe', 'qixu', 'yangxu', 'yinxu', 'tanshi', 'shire', 'xueyu', 'qiyu', 'tebing']

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
    // 只在没有进行中的作答时回显上次结果，否则会和"继续作答"提示打架
    const local = getLocalConstitution()
    if (local?.judged) lastResult.value = local
  } catch {
    error.value = '问卷加载失败，请检查网络后刷新重试'
  }
})

// 每次作答后暂存进度
watch(answers, saveProgress, { deep: true })

const cur = () => flat.value[idx.value]
const answeredCount = () => flat.value.filter(x => answers.value[x.code]?.[x.di] !== null).length

// 答题卡核心统计与分组
const firstUnansweredIdx = computed(() => {
  if (!flat.value.length) return -1
  return flat.value.findIndex(x => answers.value[x.code]?.[x.di] === null)
})

const dimensionGroups = computed(() => {
  if (!flat.value.length || !answers.value) return []
  const map = {}
  ORDER_KEYS.forEach((k) => {
    map[k] = {
      code: k,
      name: (NAME[k] || k) + '质',
      questions: [],
      answeredCount: 0,
    }
  })

  flat.value.forEach((item, i) => {
    const group = map[item.code]
    if (group) {
      const isAnswered = answers.value[item.code]?.[item.di] !== null
      if (isAnswered) group.answeredCount++
      group.questions.push({
        globalIndex: i,
        num: i + 1,
        answered: isAnswered,
        isCurrent: i === idx.value,
        val: answers.value[item.code]?.[item.di],
      })
    }
  })

  return ORDER_KEYS.map(k => map[k]).filter(g => g && g.questions.length > 0)
})

function jumpTo(targetIdx) {
  if (targetIdx < 0 || targetIdx >= flat.value.length) return
  qDir.value = targetIdx >= idx.value ? 1 : -1
  idx.value = targetIdx
  showAnswerSheet.value = false
}

function jumpToFirstUnanswered() {
  const target = firstUnansweredIdx.value
  if (target !== -1) {
    jumpTo(target)
  } else {
    showToast('全部题目已作答完毕')
  }
}

function jumpToNextUnanswered() {
  const next = flat.value.findIndex((x, i) => i > idx.value && answers.value[x.code]?.[x.di] === null)
  if (next !== -1) {
    jumpTo(next)
  } else {
    jumpToFirstUnanswered()
  }
}

let advanceTimer = null
let pickTimer = null
onUnmounted(() => {
  if (advanceTimer) clearTimeout(advanceTimer)
  if (pickTimer) clearTimeout(pickTimer)
  if (scoresCancel) scoresCancel()
})

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
  // 防双击：先清掉未生效的跳题定时器，且钳制不越界
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

// 题目卡过渡的 JS 钩子
const { enter: qEnter, leave: qLeave } = makeNavHooks({
  getDir: () => qDir.value,
  enterDx: 28, enterDy: 0, leaveDx: 20,
  enterDurT: '.2s', enterTotal: 280,
  leaveDur: '.15s', leaveTotal: 180,
})

// ---- 进度本地暂存 ----
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

async function restart() {
  if (answeredCount() > 0) {
    try {
      await showConfirmDialog({
        title: '清空重答',
        message: '确定要清空已作答的题目重新开始吗？',
        confirmButtonText: '清空重答',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }
  if (advanceTimer) { clearTimeout(advanceTimer); advanceTimer = null }
  for (const code of Object.keys(answers.value)) answers.value[code].fill(null)
  idx.value = 0
  qDir.value = 1
  result.value = null
  revealed.value = false
  clearProgress()
}

// 九维分数滚动
let scoresCancel = null
function animateScores(results) {
  if (scoresCancel) scoresCancel()
  const targets = Object.fromEntries(Object.entries(results).map(([k, v]) => [k, v.score]))
  const keys = Object.keys(targets)
  scoresCancel = tween(900, (ease) => {
    for (const k of keys) shownScores.value[k] = Math.round(targets[k] * ease)
  })
}

async function submit() {
  submitting.value = true; error.value = ''
  try {
    const res = (await submitQuiz(answers.value)).data.data
    result.value = res
    clearProgress()
    if (!forMember.value) {
      saveLocalConstitution(res.judged, res.transformed)
      recordQuizSnapshot(answers.value, false)
    }
    if (isLoggedIn()) {
      saveRecord(res.judged, res.transformed, answers.value,
                 forMember.value || null).then(() => {
        if (!forMember.value) recordQuizSnapshot(answers.value, true)
      }).catch(() => {})
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
    afterPaint(() => {
      revealed.value = true
      animateScores(res.judged.results)
    })
  } catch (e) {
    error.value = '提交失败，请检查网络后重试（您的作答已保留）'
  } finally { submitting.value = false }
}

// 答题进度百分比
const answerPercent = computed(() =>
  flat.value.length ? Math.round(answeredCount() / flat.value.length * 100) : 0)

// 主体质名
const mainName = computed(() => {
  const r = result.value
  if (!r) return ''
  if (r.main_constitution) return r.main_constitution.name
  const biased = r.judged.combined
  if (biased.length) return `${NAME[biased[0]]}质为主（兼夹${biased.length - 1}种）`
  if ((r.judged.results.pinghe?.result ?? '否') !== '否') return '平和质'
  return '多体质兼夹'
})

// 上次结果的体质名
const lrMainName = computed(() => {
  const j = lastResult.value?.judged
  if (!j) return ''
  const code = j.main || j.combined?.[0] || 'pinghe'
  return `${NAME[code] || '平和'}质`
})

// 上次结果的日期
const lrDate = computed(() => {
  const ts = lastResult.value?.ts
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日`
})
</script>

<template>
  <div class="page quiz-page">
    <!-- 结果页 -->
    <template v-if="result">
      <div class="card result-hero pop-card">
        <p class="label">您的体质倾向</p>
        <h2>{{ mainName || '多体质兼夹' }}</h2>
        <p v-if="result.main_constitution" class="principle">{{ result.main_constitution.principle }}</p>
        <p v-else class="principle">同时具有多种偏颇体质倾向，建议以「兼夹调理、温和为要」的思路选择方子，并优先改善得分最高的体质。</p>
        <div v-if="result.judged.combined.length" class="combined">
          偏颇体质：{{ result.judged.combined.map(c => NAME[c] + '质').join('、') }}
        </div>
        <div v-else class="combined">各体质得分均未达偏颇标准，保持平和即为理想状态</div>
        <div v-if="!isLoggedIn()" class="guest-claim-tip">
          <span>已保存在本机（免登录可直接用推荐）</span>
          <router-link :to="{ path: '/login', query: { redirect: '/me' } }">登录并长期归档 →</router-link>
        </div>
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

      <!-- 测评依据声明 -->
      <div class="card quiz-disclaimer rise" style="--i: 2">
        <p class="d-title"><Info :size="14" :stroke-width="2" /> 测评依据</p>
        <ul>
          <li>量表来源：《中医体质分类与判定》（中华中医药学会标准 ZYYXH/T157-2009），简称 CCMQ</li>
          <li>判定方法：九种体质转化分算法（原始分 → 转化分，≥40 分判定为"是"，30–39 分为"倾向是"）</li>
          <li>本测评仅作健康参考，不作为医学诊断或治疗依据</li>
          <li>体质非一成不变，受季节、作息、饮食、情绪等因素动态影响</li>
        </ul>
      </div>

      <div class="section-title rise" style="--i: 3">为您推荐的方子</div>
      <div class="card rise" style="--i: 4">
        <template v-if="result.recommendations.length">
          <RecipeRow v-for="r in result.recommendations" :key="r.id" :recipe="r" />
        </template>
        <p v-else class="empty" style="padding:12px 0">暂无完全匹配的方子，可到<router-link to="/recipes" style="color: var(--green-text)">方子库</router-link>按场景浏览</p>
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
      <!-- 上次结果回看：只在还没开始作答时出现 -->
      <div class="card last-result" v-if="lastResult && answeredCount() === 0">
        <span class="lr-icon"><Info :size="15" :stroke-width="2" /></span>
        <div class="lr-txt">
          <b>上次测评：{{ lrMainName }}</b>
          <span>{{ lrDate }} · 体质会随季节作息变化，可重新测一次</span>
        </div>
      </div>

      <!-- 答题控制与进度看板 -->
      <div class="card quiz-control-card">
        <div class="qc-top">
          <div class="qc-badge-wrap">
            <span class="qc-dim-tag">{{ NAME[cur()?.code] || '体质' }}质评估</span>
            <span class="qc-idx">第 <b>{{ idx + 1 }}</b> / {{ flat.length || 67 }} 题</span>
          </div>
          <button type="button" class="qc-sheet-btn pressable" @click="showAnswerSheet = true">
            <AppIcon name="book" :size="14" :stroke-width="2.2" />
            <span>答题卡 ({{ answeredCount() }}/{{ flat.length || 67 }})</span>
          </button>
        </div>

        <van-progress class="progress-line" :percentage="answerPercent" color="#359068" track-color="#eef7f2" :show-pivot="false" />

        <div class="qc-bottom">
          <span class="qc-pct">完成度 {{ answerPercent }}%</span>
          <button
            v-if="answeredCount() < flat.length"
            type="button"
            class="qc-jump-btn"
            @click="jumpToFirstUnanswered"
          >
            定位首道未答题 (第{{ firstUnansweredIdx + 1 }}题) →
          </button>
          <span v-else class="qc-all-done">全部题目已答完，可提交</span>
        </div>
      </div>

      <!-- 问卷加载中骨架 -->
      <div class="card" v-if="!flat.length && !error">
        <div class="skl q-skl-title"></div>
        <div class="q-skl-opts">
          <span class="skl q-skl-opt" v-for="n in 5" :key="n"></span>
        </div>
      </div>

      <p v-if="error && !flat.length" class="submit-error shake">{{ error }}</p>

      <!-- 题目卡：优雅卡片 + 序号/状态指示 -->
      <Transition :name="qDir === 1 ? 'q-fwd' : 'q-back'" mode="out-in"
                  :css="false" @enter="qEnter" @leave="qLeave">
        <div class="card q-card" v-if="flat.length && cur()" :key="idx">
          <div class="q-card-head">
            <span class="q-num-tag">第 {{ idx + 1 }} 题</span>
            <span class="q-dim-name">{{ NAME[cur().code] }}质</span>
            <span class="q-status-badge" :class="answers[cur().code][cur().di] !== null ? 'done' : 'pending'">
              {{ answers[cur().code][cur().di] !== null ? '已作答' : '待作答' }}
            </span>
          </div>

          <p class="q-text">{{ cur().q }}</p>

          <div class="opts">
            <button v-for="o in OPTIONS" :key="o.v" class="opt pressable"
                    :class="{ on: answers[cur().code][cur().di] === o.v, pop: justPicked === o.v }"
                    @click="choose(o.v)">
              <span class="opt-score">{{ o.v }}分</span>
              <span class="opt-label">{{ o.label }}</span>
            </button>
          </div>
        </div>
      </Transition>

      <p v-if="error && flat.length" class="submit-error shake">{{ error }}</p>

      <!-- 导航主按钮 -->
      <div class="q-nav">
        <button class="btn ghost" :disabled="idx === 0" @click="prevQ">上一题</button>
        <button class="btn" v-if="idx < flat.length - 1" @click="nextQ">下一题</button>
        <button class="btn primary-submit" v-else :disabled="answeredCount() < flat.length || submitting" @click="submit">
          <span v-if="submitting" class="spinner"></span>
          {{ submitting ? '判定中…' : answeredCount() < flat.length ? `还有 ${flat.length - answeredCount()} 题` : '查看体质结果' }}
        </button>
      </div>

      <!-- 辅助快捷栏：跳未答 / 清空 -->
      <div class="q-sub-actions">
        <button
          v-if="answeredCount() < flat.length && answers[cur()?.code]?.[cur()?.di] !== null"
          type="button"
          class="sub-act-btn pressable"
          @click="jumpToNextUnanswered"
        >
          下一道未答题 →
        </button>
        <button
          v-if="answeredCount() > 0"
          type="button"
          class="sub-act-btn danger pressable"
          @click="restart"
        >
          清空重答
        </button>
      </div>

      <p class="q-note">共 {{ flat.length || 67 }} 题，约 3 分钟。进度自动保存在本机，误关页面后重新打开可继续作答。</p>

      <!-- 家庭代测（T2-8）：结果将存入选中成员的档案 -->
      <div class="member-pick" v-if="members.length && !result">
        <span class="mp-label">替谁测评：</span>
        <button class="tag mp-tag" :class="{ active: forMember === 0 }" @click="forMember = 0">本人</button>
        <button v-for="m in members" :key="m.id" class="tag mp-tag"
                :class="{ active: forMember === m.id }" @click="forMember = m.id">{{ m.name }}</button>
      </div>

      <!-- 答题卡抽屉弹窗（按九维分类，一键直达任意题目） -->
      <van-popup
        v-model:show="showAnswerSheet"
        position="bottom"
        round
        closeable
        class="asheet-popup"
        :style="{ maxHeight: '82vh' }"
      >
        <div class="asheet-container">
          <div class="asheet-header">
            <h3>测评答题卡</h3>
            <span class="asheet-meta">已答 <b>{{ answeredCount() }}</b> / {{ flat.length }} 题（{{ answerPercent }}%）</span>
          </div>

          <!-- 状态图例与首道未答定位 -->
          <div class="asheet-legend-bar">
            <div class="asheet-legends">
              <span class="leg-item"><i class="leg-dot done"></i>已答</span>
              <span class="leg-item"><i class="leg-dot current"></i>当前</span>
              <span class="leg-item"><i class="leg-dot pending"></i>未答</span>
            </div>
            <button
              v-if="firstUnansweredIdx !== -1"
              type="button"
              class="asheet-jump-lead pressable"
              @click="jumpToFirstUnanswered"
            >
              跳至首道未答 (第{{ firstUnansweredIdx + 1 }}题)
            </button>
          </div>

          <!-- 九大体质维度分组 -->
          <div class="asheet-groups-scroll">
            <div v-for="g in dimensionGroups" :key="g.code" class="asheet-dim-block">
              <div class="asheet-dim-title">
                <span class="dim-label">{{ g.name }}</span>
                <span class="dim-prog" :class="{ finished: g.answeredCount === g.questions.length }">
                  {{ g.answeredCount }}/{{ g.questions.length }}
                </span>
              </div>
              <div class="asheet-num-grid">
                <button
                  v-for="q in g.questions"
                  :key="q.globalIndex"
                  type="button"
                  class="asheet-num-btn pressable"
                  :class="{
                    done: q.answered,
                    current: q.isCurrent,
                    pending: !q.answered,
                  }"
                  @click="jumpTo(q.globalIndex)"
                >
                  {{ q.num }}
                </button>
              </div>
            </div>
          </div>

          <div class="asheet-footer">
            <button
              type="button"
              class="btn block"
              :disabled="answeredCount() < flat.length || submitting"
              @click="showAnswerSheet = false; if (answeredCount() === flat.length) submit();"
            >
              {{ answeredCount() < flat.length ? `还有 ${flat.length - answeredCount()} 题未作答` : '全部完成，查看体质结果' }}
            </button>
          </div>
        </div>
      </van-popup>
    </template>
  </div>
</template>

<style scoped>
.quiz-page { max-width: 680px; margin: 0 auto; }

/* 答题控制与进度卡片 */
.quiz-control-card {
  padding: 12px 14px;
  margin-bottom: 12px;
  background-color: var(--card);
}
.qc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 9px;
}
.qc-badge-wrap {
  display: flex;
  align-items: center;
  gap: 7px;
}
.qc-dim-tag {
  font-size: 11.5px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--green-100);
  color: var(--green-text);
}
.qc-idx {
  font-size: 13px;
  color: var(--ink-600);
}
.qc-idx b {
  color: var(--green-900);
}
.qc-sheet-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--green-200);
  background: var(--green-50);
  color: var(--green-text);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--dur-fast) ease;
}
.qc-sheet-btn:hover {
  background: var(--green-100);
  border-color: var(--green-600);
}

.progress-line { height: 5px; margin: 2px 0 7px; }
.progress-line :deep(.van-progress__portion) { border-radius: 3px; transition: width var(--dur-med) var(--ease-out-soft); }

.qc-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11.5px;
  color: var(--ink-400);
}
.qc-jump-btn {
  background: none;
  border: none;
  color: var(--green-text);
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}
.qc-jump-btn:hover {
  text-decoration: underline;
}
.qc-all-done {
  color: var(--green-text);
  font-weight: 600;
}

/* 上次结果回看条 */
.last-result { display: flex; align-items: center; gap: 10px; padding: 12px 14px; margin-bottom: 12px; }
.lr-icon {
  flex-shrink: 0; width: 30px; height: 30px; border-radius: 50%;
  background: var(--green-50); border: 1px solid var(--green-100);
  display: flex; align-items: center; justify-content: center; color: var(--green-text);
}
.lr-txt { min-width: 0; }
.lr-txt b { display: block; font-size: 13.5px; color: var(--ink-900); }
.lr-txt span { font-size: 11.5px; color: var(--ink-400); }

/* 题目卡 */
.q-card {
  padding: 16px 14px 18px;
  margin-bottom: 14px;
}
.q-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.q-num-tag {
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-400);
}
.q-dim-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--green-text);
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--green-50);
}
.q-status-badge {
  margin-left: auto;
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.q-status-badge.done {
  background: var(--green-100);
  color: var(--green-text);
}
.q-status-badge.pending {
  background: var(--amber-50);
  color: var(--amber-text);
}

.q-text {
  font-family: var(--font-serif);
  font-size: 17.5px;
  font-weight: 600;
  line-height: 1.6;
  min-height: 64px;
  color: var(--ink-900);
  margin-bottom: 8px;
}

/* 题目卡过渡视觉由 qEnter/qLeave JS 钩子内联驱动 */
/* 卡片滑入/滑出的 translate(±28px) 会让 scrollWidth 瞬时涨到 388px（375 视口下横向抖动，
   实测 2026-11-07）。overflow-x: clip 裁掉瞬时溢出且不产生滚动容器，静止态零差异 */
.page { overflow-x: clip; }

.opts { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 10px; }
.opt {
  border: 1px solid var(--green-100);
  background: var(--card);
  border-radius: 10px;
  padding: 10px 2px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  cursor: pointer;
  transition: background var(--dur-fast) ease, color var(--dur-fast) ease, border-color var(--dur-fast) ease, scale var(--dur-fast) var(--ease-snap);
}
.opt-score {
  font-size: 10px;
  opacity: 0.65;
  line-height: 1;
}
.opt-label {
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.2;
}
.opt:active { scale: 0.94; }
.opt.on {
  background: var(--green-700);
  color: #fff;
  border-color: var(--green-700);
  font-weight: 600;
}
.opt.on .opt-score {
  opacity: 0.85;
}
.opt.pop { animation: pop 0.45s var(--ease-spring); }

.q-nav { display: flex; gap: 10px; margin-top: 12px; }
.q-nav .btn { flex: 1; text-align: center; }

.q-sub-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
}
.sub-act-btn {
  background: none;
  border: none;
  color: var(--green-text);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  padding: 4px 0;
}
.sub-act-btn:hover { text-decoration: underline; }
.sub-act-btn.danger { color: var(--red-text); }

.submit-error { margin-top: 12px; padding: 10px 12px; background: var(--red-50); color: var(--red-text); border-radius: 10px; font-size: 13px; }
.q-note { font-size: 11px; color: var(--ink-400); margin-top: 12px; line-height: 1.5; }
.member-pick { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
.mp-label { font-size: 12px; color: var(--ink-400); }
.mp-tag { cursor: pointer; }
.mp-tag.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }

/* 问卷加载骨架 */
.q-skl-title { height: 48px; margin: 12px 0 4px; }
.q-skl-opts { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 12px; }
.q-skl-opt { height: 42px; border-radius: 10px; }

/* 结果页揭示 */
.result-hero { text-align: center; padding: 26px 16px; animation: rise .5s var(--ease-out-soft) backwards; }
.result-hero .label { font-size: 12px; color: var(--ink-400); }
.result-hero h2 { font-family: var(--font-serif); font-size: 26px; font-weight: 700; color: var(--green-text); margin: 6px 0; animation: pop .55s var(--ease-spring) .25s backwards; }
.result-hero .principle { font-size: 13px; color: var(--ink-600); }
.combined { margin-top: 8px; font-size: 12px; color: var(--amber-text); }
.guest-claim-tip {
  margin-top: 12px; padding: 8px 12px; border-radius: 9px;
  background: var(--green-50); border: 1px solid var(--green-100);
  font-size: 12px; color: var(--ink-600);
  display: inline-flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 4px 10px;
}
.guest-claim-tip a { color: var(--green-text); font-weight: 600; text-decoration: none; }
.guest-claim-tip a:hover { text-decoration: underline; }

.score-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
.s-name { width: 42px; font-size: 13px; color: var(--ink-600); }
.s-bar { flex: 1; }
.s-bar :deep(.van-progress__portion) { transition: width var(--dur-slow) var(--ease-out-soft); }
.s-val { width: 34px; text-align: right; font-size: 12px; color: var(--ink-600); font-variant-numeric: tabular-nums; }
.s-tag { width: 44px; font-size: 11px; color: var(--ink-400); text-align: center; }
.s-tag.hit { color: var(--green-text); font-weight: 600; }

.diet-ref p { font-size: 13px; color: var(--ink-600); line-height: 1.7; }

/* 测评依据声明 */
.quiz-disclaimer { background: var(--green-50); border: 1px dashed var(--green-200); }
.quiz-disclaimer .d-title { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--green-700); margin: 0 0 8px; }
.quiz-disclaimer ul { margin: 0; padding-left: 18px; }
.quiz-disclaimer li { font-size: 12px; color: var(--ink-600); line-height: 1.8; }

/* ===== 答题卡抽屉弹窗样式 ===== */
.asheet-container {
  padding: 18px 16px 20px;
  max-width: 600px;
  margin: 0 auto;
}
.asheet-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding-bottom: 8px;
}
.asheet-header h3 {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--ink-900);
  margin: 0;
}
.asheet-meta {
  font-size: 12px;
  color: var(--ink-400);
}
.asheet-meta b {
  color: var(--green-text);
}

.asheet-legend-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 0 10px;
  border-bottom: 1px solid var(--green-100);
}
.asheet-legends {
  display: flex;
  align-items: center;
  gap: 12px;
}
.leg-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: var(--ink-600);
}
.leg-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}
.leg-dot.done {
  background: var(--green-700);
}
.leg-dot.current {
  background: var(--amber-500);
  box-shadow: 0 0 0 2px rgba(184, 124, 46, 0.25);
}
.leg-dot.pending {
  background: var(--card);
  border: 1px dashed var(--ink-400);
}

.asheet-jump-lead {
  font-size: 11.5px;
  color: var(--green-text);
  background: var(--green-50);
  border: 1px solid var(--green-200);
  border-radius: 999px;
  padding: 3px 9px;
  cursor: pointer;
  font-weight: 600;
}
.asheet-jump-lead:hover {
  background: var(--green-100);
}

.asheet-groups-scroll {
  max-height: 50vh;
  overflow-y: auto;
  padding: 12px 2px;
}
.asheet-dim-block {
  margin-bottom: 14px;
}
.asheet-dim-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-900);
  margin-bottom: 6px;
}
.dim-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.dim-prog {
  font-size: 11px;
  color: var(--ink-400);
  font-weight: 500;
}
.dim-prog.finished {
  color: var(--green-text);
  font-weight: 700;
}

.asheet-num-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 6px;
}
@media (max-width: 480px) {
  .asheet-num-grid {
    grid-template-columns: repeat(7, 1fr);
    gap: 5px;
  }
}
.asheet-num-btn {
  height: 34px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--card-border);
  background: var(--card);
  color: var(--ink-600);
  cursor: pointer;
  transition: all var(--dur-fast) ease;
}
.asheet-num-btn.done {
  background: var(--green-700);
  color: #fff;
  border-color: var(--green-700);
}
.asheet-num-btn.current {
  border-color: var(--amber-600);
  box-shadow: 0 0 0 2px var(--amber-500);
  font-weight: 700;
}
.asheet-num-btn.pending {
  border-style: dashed;
  color: var(--ink-400);
}
.asheet-num-btn:hover {
  transform: translateY(-1px);
}

.asheet-footer {
  padding-top: 12px;
  border-top: 1px solid var(--card-border);
}
</style>
