<script setup>
import { ref, markRaw, onMounted } from 'vue'
import { Leaf, Eye, Moon, CupSoda, LeafyGreen, Flower2 } from '@lucide/vue'
import { getStats, listRecipes, matImg } from '../api'
import { useCountUp } from '../utils/motion'
import TextReveal from '../components/TextReveal.vue'

const stats = ref(null)
const showcaseRecipes = ref([])   // 证据链专区示例方
const sleepRecipes = ref([])
const daily = ref(null)        // 今日推荐
const coverTry = ref(0)
const cover = ref('')

const scenes = [
  { name: '护嗓润喉', desc: '咽干用嗓多', icon: markRaw(Leaf) },
  { name: '熬夜护眼', desc: '屏幕眼干涩', icon: markRaw(Eye) },
  { name: '助眠', desc: '多梦入睡难', icon: markRaw(Moon) },
  { name: '消化', desc: '餐后腹胀腻', icon: markRaw(CupSoda) },
  { name: '换季调理', desc: '季节交替期', icon: markRaw(LeafyGreen) },
  { name: '经期温养', desc: '温和补养', icon: markRaw(Flower2) },
]

// 时令场景横滑卡（配图 → 场景第一个方子的首味配料图，无则渐变兜底）
const SEASON_SCENES = [
  { name: '换季调理', img: '百合', count: 25 },
  { name: '护嗓润喉', img: '金银花', count: 13 },
  { name: '助眠', img: '酸枣仁', count: 13 },
  { name: '消化', img: '山楂', count: 11 },
  { name: '熬夜护眼', img: '枸杞子', count: 10 },
  { name: '经期温养', img: '大枣', count: 9 },
]

onMounted(async () => {
  const [statsR, showcaseR, sleepR] = await Promise.allSettled([
    getStats(),
    listRecipes({ size: 3 }),
    listRecipes({ scene: '助眠', size: 3 }),
  ])
  if (statsR.status === 'fulfilled') {
    stats.value = statsR.value.data.data
  }
  if (showcaseR.status === 'fulfilled') showcaseRecipes.value = showcaseR.value.data.data.items
  if (sleepR.status === 'fulfilled') sleepRecipes.value = sleepR.value.data.data.items

  // 今日推荐：按日期在全部方子里轮换，每天一款
  try {
    const all = (await listRecipes({ size: 100 })).data.data.items
    if (all.length) {
      const day = Math.floor(Date.now() / 86400000)
      daily.value = all[day % all.length]
    }
  } catch { /* 推荐失败不影响首页 */ }
})

// hero 数字滚动（useCountUp：stats 到位后 source 有值即滚动）
const statSource = ref({ recipe: 0, compound: 0, target: 0 })
const animatedStats = useCountUp(statSource, 800)
function onStats(s) {
  statSource.value = { ...s }
}

// hero 光斑跟随：桌面端 pointermove 写 CSS 变量（移动端无 hover 不启用）
const heroEl = ref(null)
function heroGlow(e) {
  const el = heroEl.value
  if (!el) return
  const r = el.getBoundingClientRect()
  el.style.setProperty('--mx', (e.clientX - r.left) + 'px')
  el.style.setProperty('--my', (e.clientY - r.top) + 'px')
}

function onDailyImgErr() {
  const mats = daily.value?.materials || []
  coverTry.value += 1
  cover.value = coverTry.value < mats.length ? matImg(mats[coverTry.value]) : ''
}
</script>

<template>
  <div class="page">
    <!-- hero -->
    <div class="hero card" ref="heroEl" @pointermove="heroGlow">
      <div class="hero-glow" aria-hidden="true"></div>
      <h1><TextReveal text="药食同源 · 有据可查" /><br/><TextReveal text="每杯茶饮都有「成分说明书」" :delay="300" /></h1>
      <p class="sub">基于大创课题「中药入血成分预测」成果<br/>从体质测评到方子推荐，活性成分、入血概率、作用靶点全程有据可查</p>
      <div class="hero-btns">
        <router-link to="/quiz" class="btn">开始体质测评</router-link>
        <router-link to="/recipes" class="btn ghost">逛方子库</router-link>
      </div>
      <div v-if="stats" class="hero-stats">
        <div><b>{{ animatedStats.recipe ?? 0 }}</b><span>食养方</span></div>
        <div><b>{{ animatedStats.compound ?? 0 }}</b><span>活性成分</span></div>
        <div><b>{{ animatedStats.target ?? 0 }}</b><span>作用靶点</span></div>
      </div>
    </div>

    <!-- 今日推荐 -->
    <div class="section-title">今日推荐</div>
    <router-link v-if="daily" :to="`/recipes/${daily.id}`" class="card daily">
      <div class="d-cover">
        <img v-if="cover !== ''" :src="cover || matImg(daily.materials?.[0] || '')" alt="" loading="lazy" @error="onDailyImgErr" />
        <span v-else class="d-fallback">{{ (daily.materials?.[0]?.name || daily.name)[0] }}</span>
        <span class="d-type">{{ daily.type }}</span>
      </div>
      <div class="d-main">
        <b class="d-name">{{ daily.name }}</b>
        <p class="d-one">{{ daily.oneliner }}</p>
        <div class="d-tags">
          <span v-for="s in daily.scenes.slice(0, 2)" :key="s" class="tag">{{ s }}</span>
        </div>
      </div>
    </router-link>
    <!-- 场景入口 -->
    <div class="section-title">按场景找茶饮</div>
    <div class="scene-grid">
      <router-link v-for="(s, i) in scenes" :key="s.name" :to="`/recipes?scene=${encodeURIComponent(s.name)}`" class="scene card pressable" :style="{ '--i': i }">
        <span class="scene-icon"><component :is="s.icon" :size="22" :stroke-width="1.8" /></span>
        <span class="name">{{ s.name }}</span>
        <span class="desc">{{ s.desc }}</span>
      </router-link>
    </div>

    <!-- 时令场景横滑 -->
    <div class="section-title">时令专区</div>
    <div class="season-scroll">
      <router-link v-for="s in SEASON_SCENES" :key="s.name" :to="`/recipes?scene=${encodeURIComponent(s.name)}`" class="season-card">
        <img :src="matImg(s.img)" alt="" loading="lazy" />
        <div class="s-overlay">
          <b>{{ s.name }}</b>
          <span>{{ s.count }} 方</span>
        </div>
      </router-link>
    </div>

    <!-- 成分证据链（核心差异化） -->
    <div class="section-title">每个方子，一条完整证据链</div>
    <div class="card zone">
      <p class="zone-intro">活性成分 → 预测入血概率 → 作用靶点 → 数据出处，四层可溯。成分库来自本团队大创课题自建数据库，入血概率由 PU-Learning 模型预测</p>
      <div class="chain">
        <span class="chain-step">活性成分</span><i>→</i>
        <span class="chain-step">入血概率</span><i>→</i>
        <span class="chain-step">作用靶点</span><i>→</i>
        <span class="chain-step">数据出处</span>
      </div>
      <router-link v-for="r in showcaseRecipes" :key="r.id" :to="`/recipes/${r.id}`" class="recipe-row">
        <div class="r-name">{{ r.name }}</div>
        <div class="r-one">{{ r.oneliner }}</div>
      </router-link>
      <router-link to="/recipes" class="zone-more">逛逛全部 {{ stats?.stats.recipe ?? '' }} 个方子 →</router-link>
    </div>

    <!-- 日常轻养 -->
    <div class="section-title">日常轻养</div>
    <div class="card">
      <router-link v-for="r in sleepRecipes" :key="r.id" :to="`/recipes/${r.id}`" class="recipe-row">
        <div class="r-name">{{ r.name }}</div>
        <div class="r-one">{{ r.oneliner }}</div>
      </router-link>
    </div>

    <!-- 数据资产入口 -->
    <div class="section-title">成分数据</div>
    <div class="asset-grid">
      <router-link to="/herbs" class="card asset-card">
        <b>{{ stats?.stats.herb ?? '—' }}</b>
        <span>味药材图鉴</span>
        <small>性味归经 · 功效</small>
      </router-link>
      <router-link to="/compounds" class="card asset-card">
        <b>{{ stats?.stats.compound ?? '—' }}</b>
        <span>个活性成分</span>
        <small>入血概率 · 靶点</small>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.hero { position: relative; overflow: hidden; background: linear-gradient(135deg, var(--green-700), var(--green-900)); color: #fff; border: none; }
/* hero 光斑：pointermove 写入 --mx/--my，桌面端跟随；移动端静态柔光 */
.hero-glow {
  position: absolute; inset: -40%; pointer-events: none;
  background: radial-gradient(360px circle at var(--mx, 70%) var(--my, 20%), rgba(255,255,255,.16), transparent 60%);
  opacity: 0; transition: opacity .5s ease;
}
@media (hover: hover) {
  .hero:hover .hero-glow { opacity: 1; }
}
.hero h1 { position: relative; font-size: 24px; line-height: 1.45; margin-bottom: 8px; }
.hero .sub { position: relative; font-size: 13px; opacity: .85; margin-bottom: 16px; }
.hero-btns { position: relative; display: flex; gap: 10px; margin-bottom: 16px; }
.hero .btn { background: #fff; color: var(--green-700); }
.hero .btn.ghost { background: rgba(255,255,255,.16); color: #fff; }
.hero-stats { position: relative; display: flex; gap: 8px; }
.hero-stats div { flex: 1; text-align: center; background: rgba(255,255,255,.12); border-radius: 10px; padding: 8px 4px; transition: background var(--dur-fast) ease; }
.hero-stats div:active { background: rgba(255,255,255,.22); }
.hero-stats b { display: block; font-size: 18px; font-variant-numeric: tabular-nums; }
.hero-stats span { font-size: 11px; opacity: .8; }

/* 今日推荐 */
.daily { display: flex; gap: 12px; padding: 12px; text-decoration: none; color: inherit; align-items: stretch; animation: rise .45s var(--ease-out-soft) .1s backwards; }
.d-cover { position: relative; width: 92px; min-height: 92px; border-radius: 10px; overflow: hidden; background: linear-gradient(135deg, var(--green-600), var(--green-900)); flex-shrink: 0; }
.d-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.d-fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 32px; font-weight: 700; color: rgba(255,255,255,.9); }
.d-type { position: absolute; left: 0; bottom: 0; font-size: 10px; color: #fff; background: rgba(29, 74, 56, 0.75); padding: 1px 7px; border-radius: 0 8px 0 0; }
.d-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.d-name { font-size: 16px; }
.d-one { font-size: 12.5px; color: var(--ink-600); margin: 4px 0 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.d-tags { margin-top: auto; }

.scene-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.scene { display: flex; flex-direction: column; align-items: center; padding: 14px 6px; text-decoration: none; color: inherit; animation: rise .45s var(--ease-out-soft) backwards; animation-delay: calc(var(--i) * 50ms); }
.scene-icon { display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 12px; background: var(--green-50); color: var(--green-700); margin-bottom: 8px; transition: scale var(--dur-fast) var(--ease-snap), background var(--dur-fast) ease; }
.scene:active .scene-icon { scale: 1.15; background: var(--green-100); }
.scene .name { font-size: 14px; font-weight: 600; color: var(--green-700); }
.scene .desc { font-size: 11px; color: var(--ink-400); }

/* 时令横滑 */
.season-scroll { display: flex; gap: 10px; overflow-x: auto; padding-bottom: 6px; margin: 0 -16px; padding-left: 16px; padding-right: 16px; scroll-snap-type: x mandatory; -webkit-overflow-scrolling: touch; }
.season-scroll::-webkit-scrollbar { display: none; }
.season-card {
  position: relative; flex: 0 0 128px; height: 150px; border-radius: 12px; overflow: hidden;
  scroll-snap-align: start; text-decoration: none; background: var(--green-100);
}
.season-card img { width: 100%; height: 100%; object-fit: cover; display: block; }
.s-overlay {
  position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: flex-end;
  padding: 10px; background: linear-gradient(180deg, rgba(29,74,56,0) 40%, rgba(29,74,56,.85)); color: #fff;
}
.s-overlay b { font-size: 14px; }
.s-overlay span { font-size: 11px; opacity: .85; }

.zone-intro { font-size: 12px; color: var(--ink-600); margin-bottom: 10px; }
/* 证据链四步：横向排列，移动端可换行 */
.chain { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.chain-step {
  font-size: 12px; font-weight: 600; color: var(--green-700);
  background: var(--green-50); border-radius: 8px; padding: 4px 10px;
}
.chain i { font-style: normal; color: var(--ink-400); font-size: 12px; }
.zone-more { display: block; text-align: center; font-size: 13px; color: var(--green-700); padding-top: 10px; text-decoration: none; font-weight: 600; }
.recipe-row { display: block; padding: 10px 0; border-bottom: 1px solid var(--green-50); text-decoration: none; }
.recipe-row:last-child { border-bottom: none; }
.r-name { font-weight: 600; font-size: 15px; color: var(--ink-900); }
.r-one { font-size: 12px; color: var(--ink-400); margin-top: 2px; }

/* 数据资产入口 */
.asset-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.asset-card { text-decoration: none; color: inherit; padding: 14px; margin-bottom: 0; }
.asset-card b { font-size: 24px; color: var(--green-700); display: block; font-variant-numeric: tabular-nums; }
.asset-card span { font-size: 13px; color: var(--ink-900); font-weight: 600; }
.asset-card small { display: block; font-size: 11px; color: var(--ink-400); margin-top: 2px; }

@media (min-width: 900px) {
  .scene-grid { grid-template-columns: repeat(6, 1fr); }
  .hero h1 { font-size: 32px; }
  .hero .sub { font-size: 15px; }
  /* 桌面端 3D tilt：随光斑轻微转动，与 --mx/--my 同源 */
  .hero { transform: perspective(900px) rotateX(0) rotateY(0); transition: transform .3s var(--ease-out-soft); }
  .hero:hover { transform: perspective(900px) rotateX(calc((var(--my, 50%) - 50%) / -40)) rotateY(calc((var(--mx, 50%) - 50%) / 60)); }
}
</style>
