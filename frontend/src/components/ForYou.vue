<script setup>
/**
 * 「为你推荐」（千人千面，自包含组件走 SafetyBanner 惯例：自己拉数据，调用处一行挂载）
 * 三态：登录 → GET /me/recommend（档案+收藏打卡+节气）；本地有体质暂存 → 游客推荐；
 * 都没有 → 不渲染（今日推荐区块保持原样，另出测评引导）。
 * 理由标签 reasons 由后端生成（体质相宜/当令/常看），此处只展示不编造。
 */
import { ref, onMounted } from 'vue'
import AppIcon from './AppIcon.vue'
import { getMyRecommend, guestRecommend, getLocalConstitution, isLoggedIn } from '../api'

const emit = defineEmits(['active'])   // 是否渲染出了个性化推荐（父页据此隐藏通用今日推荐）
const data = ref(null)        // 后端推荐 payload
const loading = ref(true)
const failed = ref(false)     // 拉取失败 → 整块隐藏（首页其余区块不受影响）

// 本地暂存何时可用：登录用户以后端档案为准（家庭成员代测可能不同）；游客看本地
const localJ = (!isLoggedIn()) ? getLocalConstitution() : null

onMounted(async () => {
  try {
    if (isLoggedIn()) {
      data.value = (await getMyRecommend(4)).data.data
    } else if (localJ?.judged) {
      data.value = (await guestRecommend(localJ.judged, 4)).data.data
    }
  } catch { failed.value = true }
  loading.value = false
  if (data.value?.items?.length) emit('active', true)
})

const codeOf = (name) => name ? name.replace('质', '') : ''
</script>

<template>
  <template v-if="!loading && data && data.items.length">
    <div class="section-title">
      为你推荐
      <span v-if="data.main_constitution" class="fy-badge">
        <AppIcon name="user" :size="11" /> {{ data.main_constitution }}
      </span>
    </div>
    <div class="card fy-card">
      <p class="fy-lead">
        <template v-if="data.main_constitution">根据你的体质档案与当令节气</template>
        <template v-else>根据你的测评结果与当令节气</template>
        挑的 {{ data.items.length }} 款茶饮方
      </p>
      <router-link v-for="r in data.items" :key="r.id" :to="`/recipes/${r.id}`" class="fy-row pressable">
        <div class="fy-main">
          <b class="fy-name">{{ r.name }}</b>
          <span class="fy-one">{{ r.oneliner }}</span>
          <div class="fy-reasons">
            <span v-for="(reason, i) in r.reasons" :key="i" class="fy-reason"
                  :class="{ hot: i === 0 }">{{ reason }}</span>
          </div>
        </div>
        <AppIcon name="chevron" :size="14" class="fy-arrow" />
      </router-link>
      <router-link v-if="data.main_constitution"
                   :to="{ path: '/recipes', query: { constitution: codeOf(data.main_constitution) } }"
                   class="fy-more">看更多适合{{ data.main_constitution }}的方子 →</router-link>
    </div>
  </template>
  <!-- 未测体质引导：与今日推荐并存，不渲染骨架（拉取快且失败即隐藏） -->
  <template v-else-if="!loading && !data">
    <div class="fy-guide card" v-if="!failed">
      <span class="fy-guide-icon"><AppIcon name="sparkles" :size="18" /></span>
      <div class="fy-guide-txt">
        <b>想知道哪款茶适合你？</b>
        <span>3 分钟体质测评，推荐更懂你</span>
      </div>
      <router-link to="/quiz" class="fy-guide-btn">去测评</router-link>
    </div>
  </template>
</template>

<style scoped>
.fy-badge {
  display: inline-flex; align-items: center; gap: 4px; margin-left: 8px;
  font-size: 11px; font-weight: 500; color: var(--green-text);
  background: var(--green-50); border: 1px solid var(--green-100);
  padding: 1px 8px; border-radius: 10px; vertical-align: 2px;
}
.fy-card { padding: 6px 14px; }
.fy-lead { font-size: 12px; color: var(--ink-400); padding: 8px 0 4px; }
.fy-row {
  display: flex; align-items: center; gap: 8px; text-decoration: none; color: inherit;
  padding: 10px 0; border-top: 1px dashed var(--green-100);
}
.fy-main { flex: 1; min-width: 0; }
.fy-name { display: block; font-family: var(--font-serif); font-size: 15px; color: var(--ink-900); }
.fy-one {
  display: block; font-size: 12px; color: var(--ink-600); margin-top: 1px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fy-reasons { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; }
.fy-reason {
  font-size: 10.5px; color: var(--ink-600); background: var(--green-50);
  border: 1px solid var(--green-100); border-radius: 4px; padding: 0 6px; line-height: 1.6;
}
.fy-reason.hot { color: var(--green-text); border-color: var(--green-600); font-weight: 500; }
.fy-arrow { color: var(--ink-400); flex-shrink: 0; }
.fy-more { display: block; padding: 10px 0 12px; font-size: 12.5px; color: var(--green-text); text-decoration: none; font-weight: 600; border-top: 1px dashed var(--green-100); }

/* 未测体质引导条 */
.fy-guide {
  display: flex; align-items: center; gap: 12px; padding: 14px 16px; margin-bottom: 14px;
  background: linear-gradient(135deg, var(--card) 55%, var(--green-50) 100%);
}
.fy-guide-icon {
  width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
  background: var(--green-50); border: 1px solid var(--green-100);
  display: flex; align-items: center; justify-content: center; color: var(--green-text);
}
.fy-guide-txt { flex: 1; min-width: 0; }
.fy-guide-txt b { display: block; font-family: var(--font-serif); font-size: 14px; color: var(--ink-900); }
.fy-guide-txt span { font-size: 11.5px; color: var(--ink-400); }
.fy-guide-btn {
  flex-shrink: 0; font-size: 12.5px; font-weight: 600; text-decoration: none;
  color: #fdfaf1; background: var(--green-700); border-radius: 16px; padding: 6px 14px;
}
</style>
