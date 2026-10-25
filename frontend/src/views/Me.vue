<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showSuccessToast } from 'vant'
import { currentUser, logout, listRecords, listFavorites, isLoggedIn, getHistory, clearHistory, listCheckins, listFamilyMembers, addFamilyMember, removeFamilyMember } from '../api'

const router = useRouter()
const user = currentUser()
const records = ref([])
const favorites = ref([])
const loading = ref(true)
const checkins = ref(null)   // {records, streak, total, today}

// ---- 家庭成员档案（T2-8） ----
const members = ref([])
const newMemberName = ref('')
const newMemberRelation = ref('')
const RELATIONS = ['母亲', '父亲', '孩子', '伴侣', '其他']
async function loadMembers() {
  if (!isLoggedIn()) return
  try { members.value = (await listFamilyMembers()).data.data } catch { /* 静默 */ }
}
async function addMember() {
  const name = newMemberName.value.trim()
  if (!name) return
  try {
    await addFamilyMember(name, newMemberRelation.value || null)
    newMemberName.value = ''; newMemberRelation.value = ''
    showSuccessToast('已添加成员')
    loadMembers()
  } catch (e) { showFailToastSafe(e) }
}
async function delMember(m) {
  try {
    await showConfirmDialog({ title: '移除成员', message: `移除「${m.name}」？其历史测评记录会保留。` })
  } catch { return }
  try { await removeFamilyMember(m.id); loadMembers() } catch (e) { showFailToastSafe(e) }
}
function showFailToastSafe(e) {
  import('vant').then(({ showFailToast }) =>
    showFailToast(e?.response?.data?.detail || '操作失败'))
}

// ---- 设置（纯本地，未登录可用） ----
const FONT_KEYS = ['standard', 'large', 'xlarge']
const FONT_LABELS = { standard: '标准', large: '大', xlarge: '特大' }
const fontScale = ref(localStorage.getItem('shiyang_fontscale') || 'standard')
const darkMode = ref(localStorage.getItem('shiyang_theme') === 'dark')

function setFontScale(v) {
  fontScale.value = v
  localStorage.setItem('shiyang_fontscale', v)
  document.documentElement.dataset.fontsize = v
}
// 暗色模式切换：支持 View Transitions 的浏览器做「从开关位置圆形扩散」，
// 不支持的直接切换（startViewTransition 不存在时行为与原来一致）
function toggleDark(v, ev) {
  darkMode.value = v
  localStorage.setItem('shiyang_theme', v ? 'dark' : 'light')
  const apply = () => {
    document.documentElement.classList.toggle('van-theme-dark', v)
    document.documentElement.dataset.theme = v ? 'dark' : 'light'
  }
  if (document.startViewTransition && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    // 圆形扩散：以开关中心为圆心，扩散半径盖住全屏对角线
    const btn = ev?.currentTarget
    const x = btn ? btn.getBoundingClientRect().left + btn.offsetWidth / 2 : window.innerWidth - 60
    const y = btn ? btn.getBoundingClientRect().top + btn.offsetHeight / 2 : 60
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))
    const vt = document.startViewTransition(apply)
    vt.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 450, easing: 'ease-in-out', pseudoElement: '::view-transition-new(root)' }
      )
    }).catch(() => {})
  } else {
    apply()
  }
}
async function clearLocalData() {
  await showConfirmDialog({
    title: '清空本地数据',
    message: '将清除本机的测评作答缓存、浏览历史与 AI 密钥，不影响账号与收藏。',
  })
  for (const k of ['shiyang_quiz_v1', 'shiyang_history_v1', 'shiyang_ai_key']) {
    localStorage.removeItem(k)
  }
  history.value = []
  showSuccessToast('已清空')
}

// ---- 浏览历史 ----
const history = ref(getHistory())
function doClearHistory() {
  clearHistory()
  history.value = []
  showSuccessToast('浏览历史已清空')
}

const CODE_NAME = { pinghe: '平和质', qixu: '气虚质', yangxu: '阳虚质', yinxu: '阴虚质', tanshi: '痰湿质', shire: '湿热质', xueyu: '血瘀质', qiyu: '气郁质', tebing: '特禀质' }

onMounted(async () => {
  document.documentElement.dataset.fontsize = FONT_KEYS.includes(fontScale.value) ? fontScale.value : 'standard'
  if (darkMode.value) {
    document.documentElement.classList.add('van-theme-dark')
    document.documentElement.dataset.theme = 'dark'
  }
  if (!isLoggedIn()) { router.push('/login'); return }
  loadMembers()
  try {
    const [r1, r2, r3] = await Promise.all([listRecords(), listFavorites(), listCheckins()])
    records.value = r1.data.data
    favorites.value = r2.data.data
    checkins.value = r3.data.data
  } catch (e) {
    if (e?.response?.status === 401) { logout(); router.push('/login') }
  } finally { loading.value = false }
})

// 历史对比：最近两次的九维分数差
const compare = computed(() => {
  if (records.value.length < 2) return null
  const [now, prev] = records.value
  const dims = Object.keys(now.transformed)
  return dims.map(d => ({
    dim: d, name: (CODE_NAME[d] || d).replace('质', ''),
    now: now.transformed[d], prev: prev.transformed[d],
    delta: +(now.transformed[d] - prev.transformed[d]).toFixed(1),
  }))
})

// 本周打卡：周一到今天的格子
const WEEK_LABELS = ['一', '二', '三', '四', '五', '六', '日']
const weekGrid = computed(() => {
  if (!checkins.value) return []
  const days = new Set(checkins.value.records.map(r => r.day))
  const out = []
  const now = new Date()
  const monday = new Date(now)
  monday.setDate(now.getDate() - ((now.getDay() + 6) % 7))
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    out.push({ label: WEEK_LABELS[i], iso, hit: days.has(iso), future: d > now && iso !== now.toISOString().slice(0, 10) })
  }
  return out
})
const recentCheckins = computed(() => (checkins.value?.records || []).slice(0, 5))

function doLogout() { logout(); router.push('/') }
function fmtDate(s) { return (s || '').slice(0, 16) }
function buzz(ms) {
  try { navigator.vibrate?.(ms) } catch { /* 不支持则静默 */ }
}
</script>

<template>
  <div class="page">
    <!-- 用户卡 -->
    <div class="card user-card">
      <div class="avatar">{{ (user?.nickname || user?.username || '?')[0] }}</div>
      <div class="u-info">
        <b>{{ user?.nickname || user?.username }}</b>
        <span>@{{ user?.username }}</span>
      </div>
      <button class="btn ghost" @click="doLogout">退出</button>
    </div>

    <div v-if="loading" class="card">
      <div class="sk-row sk-anim" v-for="i in 3" :key="i"></div>
    </div>

    <template v-else>
      <!-- 体质档案历史 -->
      <div class="section-title">体质档案（{{ records.length }} 次）</div>
      <div class="card" v-if="!records.length">
        <p class="empty" style="padding:12px 0">还没有测评记录</p>
        <router-link to="/quiz" class="btn block">去测评</router-link>
      </div>
      <div class="card" v-else>
        <div v-for="(r, i) in records" :key="r.id" class="rec-row">
          <span class="rec-badge" v-if="i === 0">最新</span>
          <span class="rec-badge member" v-if="r.member_name">{{ r.member_name }}</span>
          <b>{{ r.main_name }}</b>
          <span v-if="r.combined.length > 1" class="combined">兼夹{{ r.combined.join('、') }}</span>
          <span class="date">{{ fmtDate(r.created_at) }}</span>
        </div>

        <!-- 历史对比 -->
        <template v-if="compare">
          <p class="cmp-title">最近两次对比</p>
          <div v-for="c in compare" :key="c.dim" class="cmp-row">
            <span class="c-name">{{ c.name }}</span>
            <span class="c-prev">{{ c.prev }}</span>
            <span class="c-arrow">→</span>
            <span class="c-now">{{ c.now }}</span>
            <span class="c-delta" :class="{ up: c.delta > 0, down: c.delta < 0 }">
              {{ c.delta > 0 ? '+' : '' }}{{ c.delta }}
            </span>
          </div>
          <p class="cmp-note">分数下降通常意味着该体质倾向减轻（转化分越低越不明显）</p>
        </template>
      </div>

      <!-- 家庭体质档案（T2-8） -->
      <div class="section-title">家庭成员
        <router-link to="/quiz" style="margin-left: auto; font-size: 12px; font-weight: 400; color: var(--green-700); text-decoration: none;">替家人测评 →</router-link>
      </div>
      <div class="card">
        <div v-if="members.length" class="fam-list">
          <div v-for="m in members" :key="m.id" class="fam-row">
            <span class="fam-avatar" :style="{ background: m.color || 'var(--green-100)' }">{{ m.name[0] }}</span>
            <div class="fam-info">
              <b>{{ m.name }}</b>
              <span v-if="m.relation" class="fam-rel">{{ m.relation }}</span>
            </div>
            <button class="fam-del" @click="delMember(m)">移除</button>
          </div>
        </div>
        <p v-else class="empty" style="padding:8px 0 12px">还没有家庭成员，添加后可在测评页替他们答题</p>
        <div class="fam-add">
          <input v-model="newMemberName" placeholder="称呼，如：妈妈" maxlength="12" class="fam-input" />
          <select v-model="newMemberRelation" class="fam-input fam-sel">
            <option value="">关系（可选）</option>
            <option v-for="r in RELATIONS" :key="r" :value="r">{{ r }}</option>
          </select>
          <button class="btn" :disabled="!newMemberName.trim()" @click="addMember">添加</button>
        </div>
      </div>

      <!-- 饮用打卡 -->
      <div class="section-title">饮用打卡
        <router-link to="/report" style="margin-left: auto; font-size: 12px; font-weight: 400; color: var(--green-700); text-decoration: none;">周期报告 →</router-link>
      </div>
      <div class="card" v-if="checkins">
        <div class="ck-head">
          <span class="ck-streak">连续 <b>{{ checkins.streak }}</b> 天</span>
          <span class="ck-total">累计 {{ checkins.total }} 天</span>
        </div>
        <div class="ck-week">
          <div v-for="d in weekGrid" :key="d.iso" class="ck-cell" :class="{ hit: d.hit, future: d.future }">
            <span class="ck-label">{{ d.label }}</span>
            <span class="ck-dot"></span>
          </div>
        </div>
        <template v-if="recentCheckins.length">
          <p class="ck-title">最近打卡</p>
          <div v-for="(r, i) in recentCheckins" :key="i" class="ck-row">
            <router-link :to="`/recipes/${r.recipe_id}`" class="ck-name">{{ r.recipe_name }}</router-link>
            <span class="ck-day">{{ r.day }}</span>
          </div>
        </template>
        <p v-else class="ck-empty">还没有打卡记录，去方子详情页试试「今日打卡」</p>
      </div>

      <!-- 收藏 -->
      <div class="section-title">我的收藏（{{ favorites.length }}）</div>
      <div class="card" v-if="!favorites.length">
        <p class="empty" style="padding:12px 0">还没有收藏，去方子库逛逛</p>
        <router-link to="/recipes" class="btn ghost block">逛方子库</router-link>
      </div>
      <div class="card" v-else>
        <router-link v-for="f in favorites" :key="f.id" :to="`/recipes/${f.id}`" class="recipe-row">
          <div class="r-name">{{ f.name }} <span class="tag warm">{{ f.type }}</span></div>
          <div class="r-one">{{ f.oneliner }}</div>
        </router-link>
      </div>

      <!-- 最近浏览（本地，未登录也可用） -->
      <div class="section-title">最近浏览</div>
      <div class="card" v-if="!history.length">
        <p class="empty" style="padding:12px 0">暂无浏览记录</p>
      </div>
      <div class="card" v-else>
        <router-link v-for="h in history.slice(0, 5)" :key="h.id" :to="`/recipes/${h.id}`" class="recipe-row">
          <div class="r-name">{{ h.name }} <span class="tag warm">{{ h.type }}</span></div>
          <div class="r-one">{{ h.oneliner }}</div>
        </router-link>
        <button class="btn ghost block clear-btn" @click="doClearHistory">清空浏览历史</button>
      </div>

      <!-- 设置 -->
      <div class="section-title">设置</div>
      <div class="card">
        <div class="set-row">
          <span class="set-label">字号大小</span>
          <div class="seg" :style="{ '--seg-i': FONT_KEYS.indexOf(fontScale) }">
            <span class="seg-slider" aria-hidden="true"></span>
            <button v-for="k in FONT_KEYS" :key="k" class="seg-item"
                    :class="{ on: fontScale === k }" @click="setFontScale(k)">{{ FONT_LABELS[k] }}</button>
          </div>
        </div>
        <div class="set-row">
          <span class="set-label">暗色模式</span>
          <button class="switch-btn" :class="{ on: darkMode }" role="switch"
                  :aria-checked="darkMode" @click="toggleDark(!darkMode, $event)">
            <span class="knob"></span>
          </button>
        </div>
        <div class="set-row">
          <span class="set-label">本地数据</span>
          <button class="btn ghost danger" @click="clearLocalData">清空作答/历史/AI密钥</button>
        </div>
        <p class="set-note">字号与主题仅保存在本机；收藏与体质档案跟随账号。</p>
      </div>

      <!-- 开放数据 API（T1-6） -->
      <div class="section-title">开发者</div>
      <div class="card">
        <router-link to="/open-api" class="recipe-row" style="display: flex; align-items: center; gap: 8px;">
          <b>开放数据 API</b>
          <span style="font-size: 12px; color: var(--ink-400);">目录/药材/成分/靶点，免 Key 只读</span>
        </router-link>
      </div>
    </template>
  </div>
</template>

<style scoped>
.user-card { display: flex; align-items: center; gap: 14px; }
.avatar { width: 52px; height: 52px; border-radius: 50%; background: var(--green-100); color: var(--green-700); font-size: 22px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.u-info { flex: 1; }
.u-info b { font-size: 17px; display: block; }
.u-info span { font-size: 12px; color: var(--ink-400); }
.rec-row { display: flex; align-items: center; gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--green-50); }
.rec-row:last-of-type { border-bottom: none; }
.rec-badge { font-size: 10px; background: var(--green-700); color: #fff; padding: 1px 7px; border-radius: 8px; }
.rec-badge.member { background: var(--amber-600); }
.fam-list { margin-bottom: 10px; }
.fam-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--green-50); }
.fam-avatar { width: 36px; height: 36px; border-radius: 50%; color: #fff; font-size: 15px; font-weight: 700;
              display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.fam-info { flex: 1; min-width: 0; }
.fam-info b { font-size: 14px; }
.fam-rel { font-size: 11px; color: var(--ink-400); margin-left: 6px; }
.fam-del { border: none; background: none; color: var(--red-500); font-size: 12px; cursor: pointer; }
.fam-add { display: flex; gap: 6px; }
.fam-input { flex: 1; min-width: 0; border: 1.5px solid var(--green-100); border-radius: 10px; padding: 8px 10px;
             font-size: 13px; background: var(--green-50); outline: none; }
.fam-input:focus { border-color: var(--green-600); }
.fam-sel { flex: 0 0 92px; }
.rec-row b { font-size: 15px; }
.combined { font-size: 12px; color: var(--amber-600); }
.date { margin-left: auto; font-size: 12px; color: var(--ink-400); }
.cmp-title { font-size: 13px; font-weight: 700; color: var(--green-700); margin-top: 12px; }
.cmp-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: 13px; }
.c-name { width: 46px; color: var(--ink-600); }
.c-prev { width: 36px; text-align: right; color: var(--ink-400); }
.c-arrow { color: var(--ink-400); }
.c-now { width: 36px; text-align: right; font-weight: 700; }
.c-delta { width: 48px; text-align: right; }
.c-delta.up { color: var(--amber-600); }
.c-delta.down { color: var(--green-700); }
.cmp-note { font-size: 11px; color: var(--ink-400); margin-top: 6px; }
.recipe-row { display: block; padding: 10px 0; border-bottom: 1px solid var(--green-50); text-decoration: none; }
.recipe-row:last-of-type { border-bottom: none; }
.r-name { font-weight: 600; font-size: 15px; color: var(--ink-900); }
.r-one { font-size: 12px; color: var(--ink-400); margin-top: 2px; }

.clear-btn { margin-top: 10px; font-size: 13px; padding: 8px 0; }

/* 打卡 */
.ck-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }
.ck-streak { font-size: 13px; color: var(--ink-600); }
.ck-streak b { font-size: 20px; color: var(--green-700); font-variant-numeric: tabular-nums; }
.ck-total { font-size: 12px; color: var(--ink-400); }
.ck-week { display: flex; justify-content: space-between; gap: 4px; margin-bottom: 10px; }
.ck-cell { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 5px; }
.ck-label { font-size: 11px; color: var(--ink-400); }
.ck-dot { width: 22px; height: 22px; border-radius: 50%; background: var(--green-50); border: 1px solid var(--green-100); position: relative; transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease; }
.ck-cell.hit .ck-dot { background: var(--green-600); border-color: var(--green-600); animation: pop .45s var(--ease-spring); }
.ck-cell.hit .ck-dot::after { content: ""; position: absolute; left: 7px; top: 3px; width: 5px; height: 9px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); }
.ck-cell.future { opacity: .35; }
.ck-title { font-size: 12px; color: var(--green-700); font-weight: 700; margin: 8px 0 2px; }
.ck-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px dashed var(--green-50); font-size: 13px; }
.ck-row:last-of-type { border-bottom: none; }
.ck-name { color: var(--ink-900); text-decoration: none; font-weight: 600; }
.ck-day { font-size: 11px; color: var(--ink-400); }
.ck-empty { font-size: 12px; color: var(--ink-400); padding: 6px 0; }

/* 设置卡片 */
.set-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--green-50); }
.set-row:last-of-type { border-bottom: none; }
.set-label { font-size: 14px; color: var(--ink-900); }
/* 字号分段控件：三档等宽（1fr），滑块按 --seg-i 平移一格 */
.seg { position: relative; display: grid; grid-template-columns: repeat(3, 1fr); background: var(--green-50); border-radius: 10px; padding: 3px; }
.seg-slider {
  position: absolute; top: 3px; bottom: 3px; left: 3px; border-radius: 8px;
  background: var(--green-700);
  width: calc((100% - 6px) / 3);
  translate: calc(var(--seg-i, 0) * 100%) 0;
  transition: translate var(--dur-med) var(--ease-spring);
}
.seg-item { position: relative; z-index: 1; border: none; background: transparent; padding: 6px 14px; font-size: 13px; color: var(--ink-600); border-radius: 8px; cursor: pointer; transition: color var(--dur-fast) ease; white-space: nowrap; }
.seg-item.on { color: #fff; font-weight: 600; }
.switch-btn { width: 46px; height: 26px; border-radius: 13px; border: none; background: #d7e0db; position: relative; cursor: pointer; transition: background .2s; }
.switch-btn.on { background: var(--green-600); }
.switch-btn .knob { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; transition: left .2s var(--ease-spring); }
.switch-btn.on .knob { left: 23px; }
.btn.danger { color: var(--red-500); background: var(--red-50); font-size: 13px; padding: 7px 12px; }
.set-note { font-size: 11px; color: var(--ink-400); margin-top: 10px; }

/* 骨架屏 */
.sk-row { height: 16px; border-radius: 8px; margin: 14px 0; }
.sk-row:first-child { margin-top: 0; }
.sk-row:last-child { margin-bottom: 0; }
.sk-anim { background: linear-gradient(90deg, var(--green-50) 25%, #e6f1ea 50%, var(--green-50) 75%); background-size: 200% 100%; animation: shimmer 1.3s infinite; }
</style>
