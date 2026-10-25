<script setup>
import { ref, markRaw, onMounted } from 'vue'
import { Leaf, Eye, Moon, CupSoda, LeafyGreen, Flower2 } from '@lucide/vue'
import { getStats, listRecipes } from '../api'

const stats = ref(null)
const throatRecipes = ref([])
const sleepRecipes = ref([])

const scenes = [
  { name: '护嗓润喉', desc: '咽干用嗓多', icon: markRaw(Leaf) },
  { name: '熬夜护眼', desc: '屏幕眼干涩', icon: markRaw(Eye) },
  { name: '助眠', desc: '多梦入睡难', icon: markRaw(Moon) },
  { name: '消化', desc: '餐后腹胀腻', icon: markRaw(CupSoda) },
  { name: '换季调理', desc: '季节交替期', icon: markRaw(LeafyGreen) },
  { name: '经期温养', desc: '温和补养', icon: markRaw(Flower2) },
]

onMounted(async () => {
  const [statsR, throatR, sleepR] = await Promise.allSettled([
    getStats(),
    listRecipes({ scene: '护嗓润喉', size: 3 }),
    listRecipes({ scene: '助眠', size: 3 }),
  ])
  if (statsR.status === 'fulfilled') stats.value = statsR.value.data.data
  if (throatR.status === 'fulfilled') throatRecipes.value = throatR.value.data.data.items
  if (sleepR.status === 'fulfilled') sleepRecipes.value = sleepR.value.data.data.items
})</script>

<template>
  <div class="page">
    <!-- hero -->
    <div class="hero card">
      <h1>呼吸道与咽喉养护<br/>每杯茶饮都有「成分说明书」</h1>
      <p class="sub">基于大创课题「中药入血成分预测」成果<br/>从体质测评到方子推荐，活性成分、入血概率、作用靶点全程有据可查</p>
      <div class="hero-btns">
        <router-link to="/quiz" class="btn">开始体质测评</router-link>
        <router-link to="/recipes?scene=护嗓润喉" class="btn ghost">看护嗓专区</router-link>
      </div>
      <div v-if="stats" class="hero-stats">
        <div><b>{{ stats.stats.recipe }}</b><span>食养方</span></div>
        <div><b>{{ stats.stats.compound }}</b><span>活性成分</span></div>
        <div><b>{{ stats.stats.target }}</b><span>作用靶点</span></div>
      </div>
    </div>

    <!-- 场景入口 -->
    <div class="section-title">按场景找茶饮</div>
    <div class="scene-grid">
      <router-link v-for="s in scenes" :key="s.name" :to="`/recipes?scene=${encodeURIComponent(s.name)}`" class="scene card">
        <span class="scene-icon"><component :is="s.icon" :size="22" :stroke-width="1.8" /></span>
        <span class="name">{{ s.name }}</span>
        <span class="desc">{{ s.desc }}</span>
      </router-link>
    </div>

    <!-- 呼吸健康专区（核心定位） -->
    <div class="section-title">呼吸健康专区 · 咽喉养护</div>
    <div class="card zone">
      <p class="zone-intro">咽喉是呼吸道的门户。本专区每个方子附三维机制参考（抗炎 / 免疫调节 / 气道修复），与大创课题「中医治疗儿童哮喘作用机制分析」一脉相承</p>
      <router-link v-for="r in throatRecipes" :key="r.id" :to="`/recipes/${r.id}`" class="recipe-row">
        <div class="r-name">{{ r.name }}</div>
        <div class="r-one">{{ r.oneliner }}</div>
      </router-link>
      <router-link to="/recipes?scene=护嗓润喉" class="zone-more">查看全部护嗓方 →</router-link>
    </div>

    <!-- 日常轻养 -->
    <div class="section-title">日常轻养</div>
    <div class="card">
      <router-link v-for="r in sleepRecipes" :key="r.id" :to="`/recipes/${r.id}`" class="recipe-row">
        <div class="r-name">{{ r.name }}</div>
        <div class="r-one">{{ r.oneliner }}</div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.hero { background: linear-gradient(135deg, var(--green-700), var(--green-900)); color: #fff; border: none; }
.hero h1 { font-size: 24px; line-height: 1.45; margin-bottom: 8px; }
.hero .sub { font-size: 13px; opacity: .85; margin-bottom: 16px; }
.hero-btns { display: flex; gap: 10px; margin-bottom: 16px; }
.hero .btn { background: #fff; color: var(--green-700); }
.hero .btn.ghost { background: rgba(255,255,255,.16); color: #fff; }
.hero-stats { display: flex; gap: 8px; }
.hero-stats div { flex: 1; text-align: center; background: rgba(255,255,255,.12); border-radius: 10px; padding: 8px 4px; }
.hero-stats b { display: block; font-size: 18px; }
.hero-stats span { font-size: 11px; opacity: .8; }

.scene-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (min-width: 900px) {
  .scene-grid { grid-template-columns: repeat(6, 1fr); }
  .hero h1 { font-size: 32px; }
  .hero .sub { font-size: 15px; }
}
.scene { display: flex; flex-direction: column; align-items: center; padding: 14px 6px; text-decoration: none; color: inherit; }
.scene-icon { display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 12px; background: var(--green-50); color: var(--green-700); margin-bottom: 8px; }
.scene .name { font-size: 14px; font-weight: 600; color: var(--green-700); }
.scene .desc { font-size: 11px; color: var(--ink-400); }

.zone-intro { font-size: 12px; color: var(--ink-600); margin-bottom: 10px; }
.zone-more { display: block; text-align: center; font-size: 13px; color: var(--green-700); padding-top: 10px; text-decoration: none; font-weight: 600; }
.recipe-row { display: block; padding: 10px 0; border-bottom: 1px solid var(--green-50); text-decoration: none; }
.recipe-row:last-child { border-bottom: none; }
.r-name { font-weight: 600; font-size: 15px; color: var(--ink-900); }
.r-one { font-size: 12px; color: var(--ink-400); margin-top: 2px; }
</style>
