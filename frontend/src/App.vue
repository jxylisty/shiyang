<script setup>
import { useRoute } from 'vue-router'
import { watch } from 'vue'
import { Leaf } from '@lucide/vue'

const route = useRoute()
watch(() => route.meta.title, (t) => { document.title = t ? `${t} · 食养有据` : '食养有据' }, { immediate: true })
</script>

<template>
  <header class="topbar">
    <router-link to="/" class="logo"><Leaf class="logo-icon" :size="20" :stroke-width="2.2" />食养有据<small>药食同源 · 成分有据</small></router-link>
    <nav>
      <router-link to="/quiz">体质测评</router-link>
      <router-link to="/recipes">方子库</router-link>
      <router-link to="/me">我的</router-link>
    </nav>
  </header>
  <router-view />
  <div class="disclaimer">本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗</div>
</template>

<style scoped>
.logo { text-decoration: none; display: inline-flex; align-items: center; }
.logo-icon { color: var(--green-600); margin-right: 6px; flex-shrink: 0; }
</style>
