<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from './components/AppIcon.vue'
import SearchBox from './components/SearchBox.vue'
import CloudDivider from './components/CloudDivider.vue'
import { makeNavHooks } from './utils/motion'
import { isElderMode, toggleElderMode } from './utils/fontScale'

const route = useRoute()
const router = useRouter()

// 桌面端顶栏完整导航
const NAV = [
  { to: '/recipes', name: '方子库', icon: 'book' },
  { to: '/pantry', name: '茶罐', icon: 'jar' },
  { to: '/herbs', name: '药材', icon: 'herb' },
  { to: '/compounds', name: '成分', icon: 'molecule' },
  { to: '/assistant', name: '问一问', icon: 'chat' },
  { to: '/me', name: '我的', icon: 'user' },
]

// 手机端底部固定大字导航栏（图标 + 清晰中文标签，解决窄屏纯图标猜谜与顶栏够不到的问题）
const MOBILE_TABS = [
  { to: '/', name: '首页', icon: 'home', match: (p) => p === '/' },
  { to: '/recipes', name: '方子库', icon: 'book', match: (p) => p.startsWith('/recipes') },
  { to: '/pantry', name: '茶罐', icon: 'jar', match: (p) => p.startsWith('/pantry') },
  { to: '/herbs', name: '药材', icon: 'herb', match: (p) => p.startsWith('/herbs') },
  { to: '/assistant', name: '问青囊', icon: 'chat', match: (p) => p.startsWith('/assistant') },
  { to: '/me', name: '我的', icon: 'user', match: (p) => ['/me', '/login', '/quiz', '/constitution', '/report', '/open-api'].some(x => p.startsWith(x)) },
]

const ROOT_PATHS = new Set(['/', '/recipes', '/pantry', '/herbs', '/compounds', '/assistant', '/me'])
const isSubPage = computed(() => !ROOT_PATHS.has(route.path))

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}

watch(() => route.meta.title, (t) => { document.title = t ? `${t} · 食养有据` : '食养有据' }, { immediate: true })

// 路由过渡 JS 钩子（setTimeout 收尾，隐藏页签不卡死）：
// router._navDir 由 router/index.js 维护，depth 变深 = 前进（新页从右滑入），变浅 = 后退
const { enter: pageEnter, leave: pageLeave } = makeNavHooks({ getDir: () => router._navDir ?? 0 })

// ./ 在 web 下等于 /，在 app(file://) 下指向包内目录
const baseUrl = import.meta.env.BASE_URL
</script>

<template>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="topbar-left">
        <button v-if="isSubPage" type="button" class="top-back pressable" @click="goBack" aria-label="返回上一页">
          <AppIcon name="back" :size="16" :stroke-width="2.3" />
          <span>返回</span>
        </button>
        <router-link to="/" class="logo">
          <AppIcon name="brand" class="logo-icon" :size="21" :stroke-width="2.1" />
          <span>食养有据</span>
          <small>药食同源 · 成分有据</small>
        </router-link>
      </div>

      <nav class="desktop-nav" aria-label="主导航">
        <router-link v-for="n in NAV" :key="n.to" :to="n.to">
          <AppIcon :name="n.icon" :size="15" :stroke-width="2" />
          <span class="nav-label">{{ n.name }}</span>
        </router-link>
      </nav>

      <div class="topbar-actions">
        <button
          type="button"
          class="elder-btn pressable"
          :class="{ on: isElderMode }"
          :aria-pressed="isElderMode"
          :title="isElderMode ? '当前为长辈大字版，点击恢复标准字号' : '开启长辈大字版（放大全站文字并精简复杂图表）'"
          @click="toggleElderMode"
        >
          <AppIcon name="fontSize" :size="14" :stroke-width="2.1" />
          <span>{{ isElderMode ? '标准字' : '长辈版' }}</span>
        </button>
        <SearchBox />
      </div>
    </div>
  </header>

  <div class="app-shell">
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
      <span class="img-credit">食材图片来自 <a href="https://commons.wikimedia.org" target="_blank" rel="noopener">Wikimedia Commons</a>（CC0 / 公有领域 / CC BY / CC BY-SA），作者与许可明细见 <a :href="`${baseUrl}img/credits.json`" target="_blank" rel="noopener">credits.json</a></span>
    </div>
  </div>

  <!-- 手机端底部固定中文导航栏（<=720px 显示） -->
  <nav class="mobile-tabbar" aria-label="手机底部导航">
    <router-link
      v-for="t in MOBILE_TABS"
      :key="t.to"
      :to="t.to"
      class="mtab-item pressable"
      :class="{ active: t.match(route.path) }"
    >
      <span class="mtab-icon">
        <AppIcon :name="t.icon" :size="20" :stroke-width="t.match(route.path) ? 2.2 : 1.85" />
      </span>
      <span class="mtab-label">{{ t.name }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.top-back {
  display: none;
  align-items: center;
  gap: 2px;
  padding: 6px 10px 6px 7px;
  border-radius: 999px;
  border: 1px solid var(--card-border);
  background: var(--card);
  color: var(--green-text);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  flex-shrink: 0;
}
.logo { text-decoration: none; display: inline-flex; align-items: center; min-width: 0; }
.logo-icon { color: var(--green-600); margin-right: 5px; flex-shrink: 0; }

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-shrink: 0;
}

/* 顶栏一键「长辈版」适老开关 */
.elder-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 11px;
  min-height: 32px;
  border-radius: 999px;
  border: 1px solid rgba(58, 122, 94, 0.28);
  background: var(--green-50);
  color: var(--green-text);
  font-size: 12.5px;
  font-weight: 600;
  font-family: inherit;
  white-space: nowrap;
  cursor: pointer;
  transition: background var(--dur-fast) ease, color var(--dur-fast) ease, border-color var(--dur-fast) ease;
}
.elder-btn:hover {
  border-color: var(--green-600);
  background: var(--green-100);
}
.elder-btn.on {
  background: var(--green-700);
  border-color: var(--green-700);
  color: #fdfaf1;
  box-shadow: 0 2px 6px rgba(42, 95, 74, 0.25);
}

/* 手机端底部固定大字导航栏 */
.mobile-tabbar {
  display: none;
}

@media (max-width: 720px) {
  /* 窄屏子页面显示清晰的「返回」按钮，防止长辈迷失在详情页 */
  .top-back {
    display: inline-flex;
  }
  .top-back + .logo .logo-icon {
    display: none;
  }

  .mobile-tabbar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 45;
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    padding: 5px 4px calc(5px + env(safe-area-inset-bottom, 0px));
    background-color: rgba(253, 250, 241, 0.96);
    background-image: var(--paper-fiber);
    background-blend-mode: multiply;
    backdrop-filter: blur(12px) saturate(1.06);
    -webkit-backdrop-filter: blur(12px) saturate(1.06);
    border-top: 1px solid var(--card-border);
    box-shadow: 0 -3px 16px rgba(74, 56, 32, 0.08);
  }

  .mtab-item {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    min-height: 50px;
    padding: 3px 2px;
    border-radius: 10px;
    text-decoration: none;
    color: var(--ink-600);
    transition: color var(--dur-fast) ease, background var(--dur-fast) ease;
  }
  .mtab-icon {
    width: 34px;
    height: 24px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: background var(--dur-fast) ease, color var(--dur-fast) ease;
  }
  .mtab-label {
    font-size: 11.5px;
    font-weight: 500;
    line-height: 1.2;
    white-space: nowrap;
  }
  .mtab-item.active {
    color: var(--green-900);
  }
  .mtab-item.active .mtab-icon {
    background: var(--green-100);
    color: var(--green-700);
  }
  .mtab-item.active .mtab-label {
    font-weight: 700;
    color: var(--green-text);
  }
  .mtab-item.active::after {
    content: "";
    position: absolute;
    bottom: 1px;
    left: 50%;
    width: 12px;
    height: 2px;
    border-radius: 999px;
    background: var(--cinnabar);
    transform: translateX(-50%);
  }
}

/* 暗色模式下的底部导航栏与返回钮适配 */
/* 注意：:global(A) B 这种写法在 scoped 块里会被 Vue SFC 编译器丢弃后代 B（实测确认：
   编译产物只剩 :root:is(...)，.mobile-tabbar 消失），必须把整条选择器写进 :global()。 */
:global(:root:is(.van-theme-dark, [data-theme="dark"]) .mobile-tabbar) {
  background-color: rgba(42, 38, 31, 0.96);
  background-blend-mode: soft-light;
  box-shadow: 0 -3px 16px rgba(0, 0, 0, 0.36);
}
:global(:root:is(.van-theme-dark, [data-theme="dark"]) .mtab-item.active .mtab-icon) {
  background: rgba(143, 201, 171, 0.16);
  color: var(--green-text);
}
:global(:root:is(.van-theme-dark, [data-theme="dark"]) .elder-btn.on) {
  color: #fdfaf1;
}

/* 长辈大字版下底部导航标签与顶栏按钮同步加大 */
:global(:root:is([data-fontsize="large"], [data-fontsize="xlarge"]) .mtab-label) {
  font-size: 13px;
  font-weight: 600;
}
:global(:root:is([data-fontsize="large"], [data-fontsize="xlarge"]) .elder-btn),
:global(:root:is([data-fontsize="large"], [data-fontsize="xlarge"]) .top-back) {
  font-size: 14px;
  min-height: 36px;
}

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
