<script setup>
/**
 * 21 天食养周期报告（T2-7）：打卡墙 + 成分/靶点覆盖 + 场景分布 + 体质曲线
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { CalendarRange } from '@lucide/vue'
import { getCycleReport, isLoggedIn } from '../api'
import ReportPoster from '../components/ReportPoster.vue'

const router = useRouter()
const report = ref(null)
const error = ref('')
const days = ref(21)
const posterShow = ref(false)

const DAYS_OPTS = [7, 21, 90]
const DAYS_LABEL = { 7: '近 7 天', 21: '近 21 天', 90: '近 90 天' }

onMounted(() => {
  if (!isLoggedIn()) { router.push({ path: '/login', query: { redirect: '/report' } }); return }
  load()
})

async function load() {
  error.value = ''
  try { report.value = (await getCycleReport(days.value)).data.data }
  catch (e) { error.value = e?.response?.status === 401 ? '请先登录' : '报告加载失败' }
}

function pickDays(d) { days.value = d; load() }

const wallCols = computed(() => {
  // 打卡墙分 7 列（按周）
  return report.value ? report.value.wall : []
})

const CNAME = { pinghe: '平和质', qixu: '气虚质', yangxu: '阳虚质', yinxu: '阴虚质',
                tanshi: '痰湿质', shire: '湿热质', xueyu: '血瘀质', qiyu: '气郁质', tebing: '特禀质' }
</script>

<template>
  <div class="page">
    <div class="card head">
      <h2><CalendarRange :size="18" /> 食养周期报告</h2>
      <div class="d-opts">
        <button v-for="d in DAYS_OPTS" :key="d" class="tag" :class="{ active: days === d }"
                @click="pickDays(d)">{{ DAYS_LABEL[d] }}</button>
        <button v-if="report" class="tag poster-btn" @click="posterShow = true">分享报告海报</button>
      </div>
    </div>

    <van-empty v-if="error" image="error" :description="error" />

    <template v-if="report">
      <!-- 概览 -->
      <div class="card ov">
        <div class="ov-item"><b>{{ report.checkin_days }}</b><span>打卡天数</span></div>
        <div class="ov-item"><b>{{ report.streak }}</b><span>连续天数</span></div>
        <div class="ov-item"><b>{{ report.recipes_tried }}</b><span>喝过方子</span></div>
        <div class="ov-item"><b>{{ report.compounds_covered }}</b><span>覆盖成分</span></div>
        <div class="ov-item"><b>{{ report.targets_covered }}</b><span>覆盖靶点</span></div>
      </div>

      <!-- 打卡墙 -->
      <div class="section-title">打卡墙</div>
      <div class="card">
        <div class="wall">
          <div v-for="w in wallCols" :key="w.day" class="cell"
               :class="{ hit: w.count > 0, hot: w.count > 1, today: w.today }"
               :title="`${w.day}：${w.count} 次`"></div>
        </div>
        <div class="wall-legend">
          <span><i class="lg hit"></i>已打卡</span>
          <span><i class="lg hot"></i>一天多方</span>
          <span><i class="lg today"></i>今天</span>
        </div>
      </div>

      <!-- 成分覆盖 -->
      <div class="section-title">成分覆盖（{{ report.compounds_covered }} 个）</div>
      <div class="card">
        <p class="hint" v-if="report.hi_blood_covered.length">
          其中高入血概率（≥70%）<b>{{ report.hi_blood_covered.length }}</b> 个：
          {{ report.hi_blood_covered.slice(0, 8).join('、') }}<span v-if="report.hi_blood_covered.length > 8"> 等</span>
        </p>
        <p class="hint" v-else>周期内暂无高入血成分覆盖</p>
      </div>

      <!-- 靶点覆盖 -->
      <div class="section-title">高频关联靶点</div>
      <div class="card">
        <div v-if="report.top_targets.length">
          <div v-for="t in report.top_targets.slice(0, 6)" :key="t.gene" class="t-row">
            <span class="t-gene">{{ t.gene }}</span>
            <div class="t-bar"><i :style="{ width: Math.min(100, t.hits * 25) + '%' }"></i></div>
            <span class="t-hits">{{ t.hits }} 次</span>
          </div>
        </div>
        <p class="hint" v-else>暂无靶点数据，去打卡积累吧</p>
      </div>

      <!-- 场景分布 -->
      <div class="section-title">场景分布</div>
      <div class="card" v-if="report.scenes_hist.length">
        <div class="chip-wrap">
          <span v-for="[s, n] in report.scenes_hist" :key="s" class="tag">{{ s }} ×{{ n }}</span>
        </div>
      </div>
      <div class="card" v-else><p class="hint">暂无记录</p></div>

      <!-- 体质曲线 -->
      <template v-if="report.constitution_curve.length >= 2">
        <div class="section-title">体质变化</div>
        <div class="card">
          <div v-for="c in report.constitution_curve" :key="c.date" class="curve-row">
            <span class="c-date">{{ c.date }}</span>
            <b class="c-main">{{ c.main_name || CNAME[c.main_code] || c.main_code }}</b>
            <span class="c-top">
              <span v-for="[dim, score] in c.top3" :key="dim" class="tag dim-tag">
                {{ CNAME[dim] || dim }} {{ Math.round(score) }}
              </span>
            </span>
          </div>
          <p class="hint">转化分（0-100）：偏颇体质 ≥40 判定为「是」，30-39 为「倾向是」</p>
        </div>
      </template>

      <p class="foot">{{ report.note }}</p>
    </template>

    <ReportPoster v-model:show="posterShow" :report="report" />
  </div>
</template>

<style scoped>
.head { padding: 18px 16px; }
.head h2 { font-size: 18px; display: flex; align-items: center; gap: 6px; color: var(--green-700); }
.d-opts { display: flex; gap: 6px; margin-top: 10px; }
.d-opts .tag { cursor: pointer; }
.d-opts .tag.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }
.poster-btn { cursor: pointer; margin-left: auto; border-color: var(--green-700); color: var(--green-700); }
.ov { display: flex; text-align: center; padding: 14px 6px; }
.ov-item { flex: 1; min-width: 0; }
.ov-item b { font-size: 20px; color: var(--green-700); display: block; }
.ov-item span { font-size: 10px; color: var(--ink-400); }

.wall { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cell { aspect-ratio: 1; border-radius: 5px; background: var(--green-50); }
.cell.hit { background: var(--green-600); }
.cell.hot { background: var(--green-900); }
.cell.today { outline: 2px solid var(--amber-600); outline-offset: 1px; }
.wall-legend { display: flex; gap: 12px; margin-top: 10px; font-size: 11px; color: var(--ink-400); }
.lg { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 3px; vertical-align: -1px; }
.lg.hit { background: var(--green-600); }
.lg.hot { background: var(--green-900); }
.lg.today { background: var(--green-50); outline: 2px solid var(--amber-600); }

.hint { font-size: 12px; color: var(--ink-600); line-height: 1.7; }
.t-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
.t-gene { font-family: ui-monospace, monospace; font-size: 12px; width: 70px; flex-shrink: 0; color: var(--ink-600); }
.t-bar { flex: 1; height: 8px; background: var(--green-50); border-radius: 4px; overflow: hidden; }
.t-bar i { display: block; height: 100%; background: var(--green-600); border-radius: 4px; }
.t-hits { font-size: 11px; color: var(--ink-400); width: 44px; text-align: right; flex-shrink: 0; }
.chip-wrap { display: flex; flex-wrap: wrap; gap: 5px; }
.curve-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px dashed var(--green-100); flex-wrap: wrap; }
.curve-row:last-of-type { border-bottom: none; }
.c-date { font-size: 12px; color: var(--ink-400); }
.c-main { font-size: 13px; }
.dim-tag { font-size: 11px; }
.foot { font-size: 11px; color: var(--ink-400); margin-top: 14px; line-height: 1.6; }
</style>
