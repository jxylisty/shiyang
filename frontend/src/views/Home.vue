<script setup>
import { ref, onMounted } from 'vue'
import AppIcon from '../components/AppIcon.vue'
import RecipeRow from '../components/RecipeRow.vue'
import { getStats, listRecipes, matImg } from '../api'
import { useCountUp } from '../utils/motion'
import TextReveal from '../components/TextReveal.vue'
import CloudDivider from '../components/CloudDivider.vue'
import HScroll from '../components/HScroll.vue'

const stats = ref(null)
const showcaseRecipes = ref([])   // 证据链专区示例方
const sleepRecipes = ref([])
const daily = ref(null)        // 今日推荐
const coverTry = ref(0)
const cover = ref('')

// 每个场景一个低饱和色调（bg 浅底 / fg 图标色），暗色模式统一回绿（见 .scene-icon 覆写）
const scenes = [
  { name: '护嗓润喉', desc: '咽干用嗓多', icon: 'throat', count: 13, bg: '#e5f3f0', fg: '#2d847b' },
  { name: '熬夜护眼', desc: '屏幕眼干涩', icon: 'eye', count: 10, bg: '#eaf0f8', fg: '#4f729f' },
  { name: '助眠', desc: '多梦入睡难', icon: 'moon', count: 13, bg: '#edeaf5', fg: '#6e629e' },
  { name: '消化', desc: '餐后腹胀腻', icon: 'fruit', count: 11, bg: '#f8f0e0', fg: '#a7722d' },
  { name: '换季调理', desc: '季节交替期', icon: 'season', count: 25, bg: '#edf4e5', fg: '#548744' },
  { name: '经期温养', desc: '温和补养', icon: 'flower', count: 9, bg: '#f8ebf0', fg: '#9e5268' },
]

// 时令场景横滑卡（配图 → 场景第一个方子的首味配料图，无则渐变兜底）
const SEASON_SCENES = [
  { name: '换季调理', img: '百合', count: 25, tag: '润燥清心' },
  { name: '护嗓润喉', img: '金银花', count: 13, tag: '生津利咽' },
  { name: '助眠', img: '酸枣仁', count: 13, tag: '养心安神' },
  { name: '消化', img: '山楂', count: 11, tag: '消食健胃' },
  { name: '熬夜护眼', img: '枸杞子', count: 10, tag: '清肝明目' },
  { name: '经期温养', img: '大枣', count: 9, tag: '温阳补血' },
]

onMounted(async () => {
  const [statsR, showcaseR, sleepR] = await Promise.allSettled([
    getStats(),
    listRecipes({ size: 3 }),
    listRecipes({ scene: '助眠', size: 3 }),
  ])
  if (statsR.status === 'fulfilled') {
    stats.value = statsR.value.data.data
    recipeSrc.value = stats.value.stats.recipe
    compoundSrc.value = stats.value.stats.compound
    targetSrc.value = stats.value.stats.target
  }
  if (showcaseR.status === 'fulfilled') showcaseRecipes.value = showcaseR.value.data.data.items
  if (sleepR.status === 'fulfilled') sleepRecipes.value = sleepR.value.data.data.items

  // 今日推荐：按日期在全部方子里轮换，每天一款
  try {
    const all = (await listRecipes({ size: 100 })).data.data.items
    if (all.length) {
      const day = Math.floor(Date.now() / 86400000)
      daily.value = all[day % all.length]
      coverTry.value = 0
      cover.value = matImg(daily.value.materials?.[0] || '')
    }
  } catch { /* 推荐失败不影响首页 */ }
})

// hero 数字滚动（useCountUp：source 有值即从当前值滚到目标）
const recipeSrc = ref(null)
const compoundSrc = ref(null)
const targetSrc = ref(null)
const animatedRecipe = useCountUp(recipeSrc, 800)
const animatedCompound = useCountUp(compoundSrc, 800)
const animatedTarget = useCountUp(targetSrc, 800)

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
      <div class="hero-seal" aria-hidden="true"><span class="seal md">食养</span></div>
      <div class="hero-body">
        <div class="hero-main">
          <div class="hero-badge"><AppIcon name="leaf" :size="13" /> 大创课题「中药入血成分预测」成果转化</div>
          <h1>
            <TextReveal text="药食同源 · 有据可查" /><br/>
            <span class="hero-subline"><TextReveal text="每杯茶饮都有「成分说明书」" :delay="300" /></span>
          </h1>
          <p class="sub">体质测评精准匹配食养方案，活性成分、入血概率、作用靶点全程可溯</p>
          <div class="hero-btns">
            <router-link to="/quiz" class="btn">开始体质测评</router-link>
            <router-link to="/recipes" class="btn ghost">逛方子库</router-link>
          </div>
        </div>
        <div v-if="stats" class="hero-stats">
          <div class="h-stat-pod">
            <div class="h-stat-icon"><AppIcon name="book" :size="18" /></div>
            <div class="h-stat-info">
              <b>{{ animatedRecipe }}</b>
              <span>经典食养方</span>
              <small>茶饮 · 药膳细分</small>
            </div>
          </div>
          <div class="h-stat-pod">
            <div class="h-stat-icon"><AppIcon name="molecule" :size="18" /></div>
            <div class="h-stat-info">
              <b>{{ animatedCompound }}</b>
              <span>测算活性成分</span>
              <small>PU-Learning 入血预测</small>
            </div>
          </div>
          <div class="h-stat-pod">
            <div class="h-stat-icon"><AppIcon name="herb" :size="18" /></div>
            <div class="h-stat-info">
              <b>{{ animatedTarget }}</b>
              <span>关联生物靶点</span>
              <small>通路富集机制透视</small>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 今日推荐 -->
    <div class="section-title">今日推荐</div>
    <router-link v-if="daily" :to="`/recipes/${daily.id}`" class="card daily pressable">
      <!-- 水印暗字：笺纸上的淡墨大字，宽屏留白处的主要视觉填充 -->
      <span class="d-watermark" aria-hidden="true">食养</span>
      <div class="d-cover">
        <img v-if="cover" :src="cover" alt="" loading="lazy" @error="onDailyImgErr" />
        <span v-else class="d-fallback"><AppIcon :name="daily.type === '药膳' ? 'dish' : 'tea'" :size="36" /></span>
        <span class="d-type">{{ daily.type }}</span>
      </div>
      <div class="d-main">
        <div class="d-head">
          <span class="d-badge"><AppIcon name="sparkles" :size="12" /> 今日食养甄选</span>
        </div>
        <b class="d-name">{{ daily.name }}</b>
        <p class="d-one">{{ daily.oneliner }}</p>
        <div class="d-tags">
          <span v-for="s in daily.scenes.slice(0, 3)" :key="s" class="tag">{{ s }}</span>
          <span v-if="daily.materials?.length" class="d-mat-hint">配料：{{ daily.materials.slice(0, 3).join(' · ') }}</span>
        </div>
      </div>
    </router-link>

    <!-- 场景入口 -->
    <div class="section-title">按场景找茶饮</div>
    <div class="scene-grid">
      <router-link v-for="(s, i) in scenes" :key="s.name" :to="`/recipes?scene=${encodeURIComponent(s.name)}`" class="scene card pressable" :style="{ '--i': i, '--tint-bg': s.bg, '--tint-fg': s.fg }">
        <span class="scene-icon"><AppIcon :name="s.icon" :size="22" /></span>
        <span class="name">{{ s.name }}</span>
        <span class="desc">{{ s.desc }}</span>
        <span class="scene-foot">{{ s.count }} 方<AppIcon name="chevron" :size="11" :stroke-width="2.4" /></span>
      </router-link>
    </div>

    <!-- 时令场景横滑（滚动条提示右侧还有内容，见 HScroll） -->
    <div class="section-title">时令专区</div>
    <HScroll class="season-wrap">
      <router-link v-for="s in SEASON_SCENES" :key="s.name" :to="`/recipes?scene=${encodeURIComponent(s.name)}`" class="season-card pressable">
        <img :src="matImg(s.img)" alt="" loading="lazy" />
        <div class="s-overlay">
          <span class="s-tag">{{ s.tag }}</span>
          <b>{{ s.name }}</b>
          <span>{{ s.count }} 款适宜方</span>
        </div>
      </router-link>
    </HScroll>

    <CloudDivider label="有据可溯" />

    <!-- 成分证据链（核心差异化） -->
    <div class="section-title">每个方子，一条完整证据链</div>
    <div class="card zone orn-lattice">
      <p class="zone-intro">活性成分 → 预测入血概率 → 作用靶点 → 数据出处，四层可溯。成分库来自本团队大创课题自建数据库，入血概率由 PU-Learning 模型预测</p>
      <div class="chain-box">
        <div class="chain-node">
          <span class="c-step">1</span>
          <span class="c-txt">活性成分</span>
        </div>
        <span class="c-arrow">→</span>
        <div class="chain-node">
          <span class="c-step">2</span>
          <span class="c-txt">入血概率</span>
        </div>
        <span class="c-arrow">→</span>
        <div class="chain-node">
          <span class="c-step">3</span>
          <span class="c-txt">作用靶点</span>
        </div>
        <span class="c-arrow">→</span>
        <div class="chain-node">
          <span class="c-step">4</span>
          <span class="c-txt">权威出处</span>
        </div>
      </div>
      <RecipeRow v-for="r in showcaseRecipes" :key="r.id" :recipe="r" />
      <router-link to="/recipes" class="zone-more">逛逛全部 {{ stats?.stats.recipe ?? '' }} 个方子 →</router-link>
    </div>

    <!-- 日常轻养 -->
    <div class="section-title">日常轻养</div>
    <div class="card">
      <RecipeRow v-for="r in sleepRecipes" :key="r.id" :recipe="r" />
    </div>

    <!-- 数据资产入口 -->
    <div class="section-title">成分数据图鉴</div>
    <div class="asset-grid">
      <router-link to="/herbs" class="card asset-card pressable orn-lattice">
        <div class="asset-icon"><AppIcon name="herb" :size="24" /></div>
        <div class="asset-info">
          <b>{{ stats?.stats.herb ?? '—' }}</b>
          <span>味药材图鉴</span>
          <small>性味归经 · 功效 · 出处</small>
        </div>
      </router-link>
      <router-link to="/compounds" class="card asset-card pressable orn-lattice">
        <div class="asset-icon"><AppIcon name="molecule" :size="24" /></div>
        <div class="asset-info">
          <b>{{ stats?.stats.compound ?? '—' }}</b>
          <span>个活性成分</span>
          <small>入血概率 · 靶点机制</small>
        </div>
      </router-link>
    </div>

    <CloudDivider />
  </div>
</template>

<style scoped>
.hero {
  position: relative; overflow: hidden;
  /* 墨绿渐层：右下沉、左上亮，模拟水墨在纸上洇开的层次 */
  background:
    radial-gradient(ellipse 90% 70% at 15% 8%, rgba(120, 168, 138, 0.28), transparent 62%),
    linear-gradient(145deg, #24493a 0%, #1a372c 52%, #14291f 100%);
  color: #f3efe2; border: 1px solid rgba(243, 239, 226, 0.14);
  box-shadow: 0 8px 26px -6px rgba(20, 41, 31, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
/* 纸纤维压在墨底上，让大块深色也有材质而非纯色块 */
.hero::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background-image: var(--paper-fiber);
  opacity: .22; mix-blend-mode: soft-light;
}
.hero-glow {
  position: absolute; inset: -40%; pointer-events: none;
  background: radial-gradient(400px circle at var(--mx, 70%) var(--my, 20%), rgba(255,255,255,.16), transparent 60%);
  opacity: 0; transition: opacity .5s ease;
}
@media (hover: hover) {
  .hero:hover .hero-glow { opacity: 1; }
}

.hero-seal { position: absolute; top: 14px; right: 14px; z-index: 2; opacity: .92; }
.hero-body { position: relative; z-index: 1; }
.hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(255, 255, 255, 0.14); backdrop-filter: blur(8px);
  padding: 3px 10px; border-radius: 14px; font-size: 11px;
  color: #d1ebd9; margin-bottom: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.hero h1 {
  font-family: var(--font-serif);
  font-size: 24px; line-height: 1.4; margin-bottom: 8px; letter-spacing: 0.03em;
}
.hero-subline { font-size: 18px; font-weight: 500; opacity: 0.92; }
.hero .sub { font-size: 13px; opacity: .88; margin-bottom: 18px; line-height: 1.55; }
.hero-btns { display: flex; gap: 10px; margin-bottom: 18px; }
.hero .btn {
  background: #fff; color: var(--green-text);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12);
}
.hero .btn:hover { background: #f5faf7; }
.hero .btn.ghost {
  background: rgba(255,255,255,.14); color: #fff; border: 1px solid rgba(255,255,255,.2);
  box-shadow: none;
}
.hero .btn.ghost:hover { background: rgba(255,255,255,.22); }

.hero-stats {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px;
}
.h-stat-pod {
  display: flex; flex-direction: column; align-items: flex-start; gap: 6px;
  background: rgba(255,255,255,.1); backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,.14);
  border-radius: 4px; padding: 9px 10px;
  min-width: 0;
  transition: background var(--dur-fast) ease, transform var(--dur-fast) ease;
}
.h-stat-pod:active { background: rgba(255,255,255,.2); }
.h-stat-icon {
  width: 26px; height: 26px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  display: flex; align-items: center; justify-content: center;
  color: #c9e8d4; flex-shrink: 0;
}
.h-stat-info { min-width: 0; width: 100%; }
.h-stat-info b { display: block; font-size: 19px; font-variant-numeric: tabular-nums; line-height: 1.1; font-family: var(--font-serif); letter-spacing: 0.02em; }
.h-stat-info span { font-size: 11px; opacity: .92; display: block; margin-top: 2px; white-space: nowrap; }
.h-stat-info small { font-size: 9.5px; opacity: .66; display: block; margin-top: 1px; line-height: 1.35; }

/* 今日推荐 */
.daily {
  display: flex; gap: 14px; padding: 14px; text-decoration: none; color: inherit;
  align-items: stretch; animation: rise .45s var(--ease-out-soft) .1s backwards;
  overflow: hidden;
}
/* 笺纸水印：淡墨衬字，宽屏留白处的主要视觉填充；移动端隐藏避免与文字抢位 */
.d-watermark {
  position: absolute; right: 28px; top: 50%; translate: 0 -50%;
  font-family: var(--font-serif); font-weight: 700;
  font-size: 54px; line-height: 1.02; letter-spacing: 0;
  color: var(--ink-900); opacity: 0.055;
  writing-mode: vertical-lr; text-orientation: upright;
  pointer-events: none; user-select: none;
  display: none;
  padding: 12px 8px;
}
/* 水印外加一圈细框，成为「印记」而非孤立的两字 */
.d-watermark::after {
  content: ""; position: absolute; inset: 0;
  border: 1px solid currentColor; border-radius: 2px; opacity: .5;
}
.d-cover {
  position: relative; width: 100px; min-height: 100px; border-radius: 12px;
  overflow: hidden; background: var(--green-100); flex-shrink: 0;
}
.d-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.d-fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--tile-ink); }
.d-type {
  position: absolute; left: 0; bottom: 0; font-size: 10px; color: #fff;
  background: rgba(22, 56, 42, 0.82); padding: 1px 8px; border-radius: 0 8px 0 0;
  backdrop-filter: blur(4px);
}
.d-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.d-head { margin-bottom: 4px; }
.d-badge {
  display: inline-flex; align-items: center; gap: 4px; font-size: 11px;
  color: var(--amber-text); background: var(--amber-50);
  padding: 1px 7px; border-radius: 6px; font-weight: 500;
}
.d-name { font-family: var(--font-serif); font-size: 17px; color: var(--ink-900); }
.d-one {
  font-size: 13px; color: var(--ink-600); margin: 4px 0 8px; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.d-tags { margin-top: auto; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.d-mat-hint { font-size: 11.5px; color: var(--ink-400); margin-left: 4px; }

/* 场景入口 */
.scene-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.scene {
  display: flex; flex-direction: column; align-items: center; padding: 15px 6px 13px;
  text-decoration: none; color: inherit; animation: rise .45s var(--ease-out-soft) backwards;
  animation-delay: calc(var(--i) * 45ms);
}
.scene-icon {
  display: flex; align-items: center; justify-content: center; width: 42px; height: 42px;
  border-radius: 50%; background: var(--tint-bg, var(--green-50)); color: var(--tint-fg, var(--tile-ink));
  box-shadow: 0 1px 4px rgba(74, 56, 32, 0.06), inset 0 0 0 1px rgba(255, 255, 255, 0.5);
  margin-bottom: 9px; transition: scale var(--dur-fast) var(--ease-snap);
  position: relative;
}
/* 圆图标外的细描边圈：古典器物常见的「双圈」感 */
.scene-icon::after {
  content: ""; position: absolute; inset: -4px; border-radius: 50%;
  border: 1px solid currentColor; opacity: .16;
}
.scene:active .scene-icon { scale: 1.12; }
:root[data-theme="dark"] .scene-icon { background: var(--green-100); color: var(--tile-ink); }
.scene .name { font-family: var(--font-serif); font-size: 14px; font-weight: 700; color: var(--ink-900); letter-spacing: 0.03em; }
.scene .desc { font-size: 10.5px; color: var(--ink-400); margin-top: 2px; }
.scene-foot {
  display: inline-flex; align-items: center; gap: 2px; margin-top: 8px;
  font-size: 10.5px; color: var(--green-text); font-variant-numeric: tabular-nums;
  background: var(--green-50); padding: 1px 7px; border-radius: 2px;
  border: 1px solid rgba(120, 95, 60, 0.1);
}

/* 时令横滑：滚动容器与滚动条由 HScroll 提供，这里只写卡片排布 */
.season-wrap :deep(.h-scroll) {
  display: flex; gap: 12px; padding-bottom: 4px;
  margin: 0 -16px; padding-left: 16px; padding-right: 16px;
  scroll-snap-type: x mandatory;
}
.season-card {
  position: relative; flex: 0 0 136px; height: 160px; border-radius: 14px; overflow: hidden;
  scroll-snap-align: start; text-decoration: none; background: var(--green-100);
  border: 1px solid var(--card-border);
  box-shadow: var(--shadow-sm);
}
.season-card img {
  width: 100%; height: 100%; object-fit: cover; display: block;
  transition: transform .4s ease;
}
.season-card:hover img { transform: scale(1.06); }
.s-overlay {
  position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: flex-end;
  padding: 10px 12px; background: linear-gradient(180deg, rgba(22,56,42,0) 30%, rgba(22,56,42,.88)); color: #fff;
}
.s-tag {
  align-self: flex-start; font-size: 9.5px; background: rgba(255,255,255,0.22);
  padding: 1px 6px; border-radius: 4px; margin-bottom: 4px; backdrop-filter: blur(4px);
}
.s-overlay b { font-family: var(--font-serif); font-size: 14.5px; }
.s-overlay span { font-size: 11px; opacity: .9; }

/* 证据链专区 */
.zone-intro { font-size: 12.5px; color: var(--ink-600); margin-bottom: 12px; line-height: 1.5; }
.chain-box {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--green-50); border: 1px solid var(--card-border);
  border-radius: 4px; padding: 10px 10px; margin-bottom: 12px;
  gap: 3px;
}
.chain-node { display: flex; align-items: center; gap: 4px; min-width: 0; }
.c-step {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; border-radius: 50%; flex-shrink: 0;
  background: var(--green-700); color: #fdfaf1; font-size: 9.5px; font-weight: 700;
}
.c-txt { font-size: 11.5px; font-weight: 600; color: var(--green-text); white-space: nowrap; }
.c-arrow { color: var(--ink-400); font-size: 11px; opacity: 0.55; flex-shrink: 0; }
.zone-more {
  display: block; text-align: center; font-size: 13.5px; color: var(--green-text);
  padding: 12px 0 2px; text-decoration: none; font-weight: 600;
}

/* 数据资产入口 */
.asset-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.asset-card {
  text-decoration: none; color: inherit; padding: 16px; margin-bottom: 0;
  display: flex; align-items: center; gap: 14px;
}
.asset-icon {
  width: 44px; height: 44px; border-radius: 12px;
  background: var(--green-50); border: 1px solid var(--green-100);
  color: var(--green-text); display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.asset-info b { font-size: 24px; color: var(--green-text); display: block; font-variant-numeric: tabular-nums; line-height: 1.1; }
.asset-info span { font-size: 13.5px; color: var(--ink-900); font-weight: 600; display: block; margin-top: 2px; }
.asset-info small { display: block; font-size: 11px; color: var(--ink-400); margin-top: 2px; }

/* 宽屏桌面端适配 */
@media (min-width: 900px) {
  .hero-body { display: grid; grid-template-columns: 1.25fr 1fr; gap: 24px; align-items: center; }
  .hero-btns { margin-bottom: 0; }
  /* 宽屏下 hero 数字仍是三列并排（与移动端一致），只是放宽内边距 */
  .hero-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .h-stat-pod { padding: 10px 12px; }
  .hero h1 { font-size: 30px; }
  .hero .sub { font-size: 14px; }
  .hero { transform: perspective(900px) rotateX(0) rotateY(0); transition: transform .3s var(--ease-out-soft); }
  .hero:hover { transform: perspective(900px) rotateX(calc((var(--my, 50%) - 50%) / -40)) rotateY(calc((var(--mx, 50%) - 50%) / 60)); }

  .scene-grid { grid-template-columns: repeat(6, 1fr); gap: 12px; }
  .season-wrap :deep(.h-scroll) { margin: 0; padding-left: 0; padding-right: 0; }
  .season-card { flex: 0 0 150px; height: 175px; }

  /* 宽屏证据链：节点等分撑开，箭头居中，读起来是一条完整的链 */
  .chain-box { gap: 10px; padding: 12px 16px; }
  .chain-node { flex: 1 1 0; justify-content: flex-start; }
  .c-txt { font-size: 13px; }
  /* 宽屏列表行：名称/一句话不再被拉成一条细线，右侧时长贴住箭头 */
  .zone .recipe-row { padding: 11px 2px; }

  /* 宽屏「今日推荐」：封面放大 + 右侧水印竖排衬字，填掉右半留白 */
  .daily { padding: 18px; gap: 20px; }
  .d-cover { width: 150px; min-height: 132px; }
  .d-watermark { display: block; }
  .d-name { font-size: 21px; }
  .d-one { font-size: 13.5px; max-width: 60ch; }
  .d-main { padding-right: 96px; }
}
</style>
