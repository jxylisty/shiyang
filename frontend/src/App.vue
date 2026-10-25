<script setup>
import { useRoute, useRouter } from 'vue-router'
import { watch } from 'vue'
import { Leaf } from '@lucide/vue'

const route = useRoute()
const router = useRouter()
watch(() => route.meta.title, (t) => { document.title = t ? `${t} · 食养有据` : '食养有据' }, { immediate: true })

// 路由切换方向：depth 变深 = 前进（新页从右滑入），变浅 = 后退（从左滑入）
// router._navDir 由 router/index.js 的 beforeEach 维护
const navDir = { get value() { return router._navDir ?? 0 } }
</script>

<template>
  <header class="topbar">
    <router-link to="/" class="logo"><Leaf class="logo-icon" :size="20" :stroke-width="2.2" />食养有据<small>药食同源 · 成分有据</small></router-link>
    <nav>
      <router-link to="/recipes">方子库</router-link>
      <router-link to="/herbs">药材</router-link>
      <router-link to="/compounds">成分</router-link>
      <router-link to="/me">我的</router-link>
    </nav>
  </header>
  <router-view v-slot="{ Component }">
    <transition :name="navDir.value === 0 ? 'page-fade' : (navDir.value === 1 ? 'page-fwd' : 'page-back')" mode="out-in">
      <component :is="Component" :key="route.path" />
    </transition>
  </router-view>
  <div class="disclaimer">本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗<br/>
    <span class="img-credit">食材图片来自 <a href="https://commons.wikimedia.org" target="_blank" rel="noopener">Wikimedia Commons</a>（CC0 / 公有领域 / CC BY / CC BY-SA），作者与许可明细见 <a href="/img/credits.json" target="_blank" rel="noopener">credits.json</a></span>
  </div>
</template>

<style scoped>
.logo { text-decoration: none; display: inline-flex; align-items: center; }
.logo-icon { color: var(--green-600); margin-right: 6px; flex-shrink: 0; }
.img-credit { display: inline-block; margin-top: 2px; font-size: 11px; opacity: .85; }
.img-credit a { color: inherit; }
</style>

<style>
/* 路由切换过渡（全局：router-view 在 App 模板内）
   首次进入 / 同层切换：轻淡入；前进：从右滑入；后退：从左滑入 */
.page-fade-enter-active, .page-fade-leave-active,
.page-fwd-enter-active, .page-fwd-leave-active,
.page-back-enter-active, .page-back-leave-active { transition: opacity .18s ease, transform .22s var(--ease-out-soft); }
.page-fade-enter-from { opacity: 0; transform: translateY(6px); }
.page-fade-leave-to { opacity: 0; }
.page-fwd-enter-from { opacity: 0; transform: translateX(32px); }
.page-fwd-leave-to { opacity: 0; transform: translateX(-18px); }
.page-back-enter-from { opacity: 0; transform: translateX(-32px); }
.page-back-leave-to { opacity: 0; transform: translateX(18px); }
</style>
