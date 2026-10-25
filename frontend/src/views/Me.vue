<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { currentUser, logout, listRecords, listFavorites, isLoggedIn } from '../api'

const router = useRouter()
const user = currentUser()
const records = ref([])
const favorites = ref([])
const loading = ref(true)

const CODE_NAME = { pinghe: '平和质', qixu: '气虚质', yangxu: '阳虚质', yinxu: '阴虚质', tanshi: '痰湿质', shire: '湿热质', xueyu: '血瘀质', qiyu: '气郁质', tebing: '特禀质' }

onMounted(async () => {
  if (!isLoggedIn()) { router.push('/login'); return }
  try {
    const [r1, r2] = await Promise.all([listRecords(), listFavorites()])
    records.value = r1.data.data
    favorites.value = r2.data.data
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

function doLogout() { logout(); router.push('/') }
function fmtDate(s) { return (s || '').slice(0, 16) }
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

    <div v-if="loading" class="empty">加载中…</div>

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
.recipe-row:last-child { border-bottom: none; }
.r-name { font-weight: 600; font-size: 15px; color: var(--ink-900); }
.r-one { font-size: 12px; color: var(--ink-400); margin-top: 2px; }
</style>
