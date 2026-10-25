<script setup>
// 体质详情页：/constitution/:code，数据来自 GET /api/v1/constitution/{code}
// 测评结果页与 Me 页的体质徽章可跳转过来
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getConstitution, listRecipes } from '../api'

const route = useRoute()
const detail = ref(null)
const recipes = ref([])
const error = ref('')

onMounted(async () => {
  try {
    const d = (await getConstitution(route.params.code)).data.data
    detail.value = d
    // 拉该体质适宜的方子（列表页已支持 constitution 筛选）
    const r = (await listRecipes({ constitution: d.name.replace('质', ''), size: 6 })).data.data
    recipes.value = r.items
  } catch {
    error.value = '加载失败，请稍后重试'
  }
})
</script>

<template>
  <div class="page">
    <van-empty v-if="error" image="error" :description="error" />
    <template v-else-if="detail">
      <div class="card hero">
        <p class="label">体质详情</p>
        <h2>{{ detail.name }}</h2>
        <p class="principle" v-if="detail.principle">{{ detail.principle }}</p>
      </div>

      <div class="section-title">典型表现</div>
      <div class="card">
        <ul class="sign-list">
          <li v-for="s in detail.typical_signs" :key="s">{{ s }}</li>
        </ul>
      </div>

      <div class="section-title">食养参考</div>
      <div class="card">
        <p v-if="detail.foods_suitable?.length"><b class="ok">宜：</b>{{ detail.foods_suitable.join('、') }}</p>
        <p v-if="detail.foods_avoid?.length" style="margin-top:6px"><b class="bad">忌：</b>{{ detail.foods_avoid.join('、') }}</p>
        <p v-if="detail.tea_ideas?.length" style="margin-top:6px"><b>茶饮思路：</b>{{ detail.tea_ideas.join('；') }}</p>
      </div>

      <div class="section-title">生活建议</div>
      <div class="card" v-if="detail.lifestyle?.length">
        <ul class="sign-list">
          <li v-for="s in detail.lifestyle" :key="s">{{ s }}</li>
        </ul>
      </div>

      <div class="section-title">适宜的方子</div>
      <div class="card">
        <template v-if="recipes.length">
          <router-link v-for="r in recipes" :key="r.id" :to="`/recipes/${r.id}`" class="recipe-row">
            <div class="r-name">{{ r.name }} <span class="tag warm">{{ r.type }}</span></div>
            <div class="r-one">{{ r.oneliner }}</div>
          </router-link>
        </template>
        <p v-else class="empty" style="padding:12px 0">暂无完全匹配的方子，可到方子库按场景浏览</p>
      </div>

      <p class="ref" v-if="detail.reference_url">
        判定依据：<a :href="detail.reference_url" target="_blank" rel="noopener">中华中医药学会《中医体质分类与判定》</a>
      </p>
    </template>
    <div v-else class="empty">加载中…</div>
  </div>
</template>

<style scoped>
.hero { text-align: center; padding: 24px 16px; }
.hero .label { font-size: 12px; color: var(--ink-400); }
.hero h2 { font-size: 26px; color: var(--green-700); margin: 6px 0; }
.principle { font-size: 13px; color: var(--ink-600); }
.sign-list { list-style: none; }
.sign-list li { font-size: 13.5px; color: var(--ink-600); padding: 4px 0 4px 16px; position: relative; }
.sign-list li::before { content: ""; position: absolute; left: 2px; top: 12px; width: 6px; height: 6px; border-radius: 50%; background: var(--green-600); }
.card p { font-size: 13.5px; color: var(--ink-600); line-height: 1.7; }
.ok { color: var(--green-700); }
.bad { color: var(--red-500); }
.recipe-row { display: block; padding: 10px 0; border-bottom: 1px solid var(--green-50); text-decoration: none; }
.recipe-row:last-child { border-bottom: none; }
.r-name { font-weight: 600; font-size: 15px; color: var(--ink-900); }
.r-one { font-size: 12px; color: var(--ink-400); margin-top: 2px; }
.ref { font-size: 11px; color: var(--ink-400); margin: 14px 4px; text-align: center; }
.ref a { color: var(--ink-400); }
</style>
