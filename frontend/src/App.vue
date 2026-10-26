<script setup>
import { useRoute, useRouter } from 'vue-router'
import { watch } from 'vue'
import AppIcon from './components/AppIcon.vue'
import SearchBox from './components/SearchBox.vue'
import CloudDivider from './components/CloudDivider.vue'
import { makeNavHooks } from './utils/motion'

const route = useRoute()
const router = useRouter()

// 顶栏导航：自绘图标 + 文字（≤420px 只留图标），让人一眼看出可点
const NAV = [
  { to: '/recipes', name: '方子库', icon: 'book' },
  { to: '/pantry', name: '茶罐', icon: 'jar' },
  { to: '/herbs', name: '药材', icon: 'herb' },
  { to: '/compounds', name: '成分', icon: 'molecule' },
  { to: '/assistant', name: '问一问', icon: 'chat' },
  { to: '/me', name: '我的', icon: 'user' },
]
watch(() => route.meta.title, (t) => { document.title = t ? `${t} · 食养有据` : '食养有据' }, { immediate: true })

// 路由过渡 JS 钩子（setTimeout 收尾，隐藏页签不卡死）：
// router._navDir 由 router/index.js 维护，depth 变深 = 前进（新页从右滑入），变浅 = 后退
const { enter: pageEnter, leave: pageLeave } = makeNavHooks({ getDir: () => router._navDir ?? 0 })
</script>

<template>
  <header class="topbar">
    <router-link to="/" class="logo"><AppIcon name="leaf" class="logo-icon" :size="20" :stroke-width="2.2" />食养有据<small>药食同源 · 成分有据</small></router-link>
    <nav>
      <router-link v-for="n in NAV" :key="n.to" :to="n.to">
        <AppIcon :name="n.icon" :size="15" :stroke-width="2" /><span class="nav-label">{{ n.name }}</span>
      </router-link>
    </nav>
    <SearchBox />
  </header>
  <router-view v-slot="{ Component }">
    <!-- JS 钩子驱动（见 pageEnter/pageLeave）：setTimeout 收尾，隐藏页签不卡死 -->
    <transition :css="false" mode="out-in" @enter="pageEnter" @leave="pageLeave">
      <component :is="Component" :key="route.path" />
    </transition>
  </router-view>
  <!-- 页脚收束：回纹压边 + 云纹，给内容较少的页面（登录/测评）一个体面的结束 -->
  <footer class="site-foot">
    <div class="fret-rule tight"></div>
    <CloudDivider label="药食同源 · 有据可查" />
  </footer>
  <div class="disclaimer">本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗<br/>
    <span class="img-credit">食材图片来自 <a href="https://commons.wikimedia.org" target="_blank" rel="noopener">Wikimedia Commons</a>（CC0 / 公有领域 / CC BY / CC BY-SA），作者与许可明细见 <a href="/img/credits.json" target="_blank" rel="noopener">credits.json</a></span>
  </div>
</template>

<style scoped>
.logo { text-decoration: none; display: inline-flex; align-items: center; }
.logo-icon { color: var(--green-600); margin-right: 6px; flex-shrink: 0; }
.img-credit { display: inline-block; margin-top: 2px; font-size: 11px; opacity: .9; }
.img-credit a { color: inherit; }
.site-foot { margin: 34px 16px 0; }
/* 页脚回纹与云纹之间留出呼吸位，避免两条装饰叠在一起 */
.site-foot :deep(.fret-rule) { margin: 0 0 18px; }
.site-foot :deep(.orn-divider) { margin: 0; }
</style>

<style>
/* 页面过渡的视觉由 pageEnter/pageLeave JS 钩子内联驱动（见上） */
</style>
