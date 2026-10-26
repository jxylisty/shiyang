<script setup>
import { useRoute, useRouter } from 'vue-router'
import { watch } from 'vue'
import AppIcon from './components/AppIcon.vue'
import SearchBox from './components/SearchBox.vue'
import { makeNavHooks } from './utils/motion'

const route = useRoute()
const router = useRouter()
watch(() => route.meta.title, (t) => { document.title = t ? `${t} · 食养有据` : '食养有据' }, { immediate: true })

// 路由过渡 JS 钩子（setTimeout 收尾，隐藏页签不卡死）：
// router._navDir 由 router/index.js 维护，depth 变深 = 前进（新页从右滑入），变浅 = 后退
const { enter: pageEnter, leave: pageLeave } = makeNavHooks({ getDir: () => router._navDir ?? 0 })
</script>

<template>
  <header class="topbar">
    <router-link to="/" class="logo"><AppIcon name="leaf" class="logo-icon" :size="20" :stroke-width="2.2" />食养有据<small>药食同源 · 成分有据</small></router-link>
    <nav>
      <router-link to="/recipes">方子库</router-link>
      <router-link to="/pantry">茶罐</router-link>
      <router-link to="/herbs">药材</router-link>
      <router-link to="/compounds">成分</router-link>
      <router-link to="/me">我的</router-link>
    </nav>
    <SearchBox />
  </header>
  <router-view v-slot="{ Component }">
    <!-- JS 钩子驱动（见 pageEnter/pageLeave）：setTimeout 收尾，隐藏页签不卡死 -->
    <transition :css="false" mode="out-in" @enter="pageEnter" @leave="pageLeave">
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
.img-credit { display: inline-block; margin-top: 2px; font-size: 11px; opacity: .9; }
.img-credit a { color: inherit; }
</style>

<style>
/* 页面过渡的视觉由 pageEnter/pageLeave JS 钩子内联驱动（见上） */
</style>
