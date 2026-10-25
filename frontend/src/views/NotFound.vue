<script setup>
import EmptyState from '../components/EmptyState.vue'
</script>

<template>
  <div class="page">
    <div class="card nf">
      <EmptyState text="404 · 这个页面不存在或已被移动">
        <div class="btns">
          <router-link to="/" class="btn">回首页</router-link>
          <router-link to="/recipes" class="btn ghost">逛方子库</router-link>
        </div>
      </EmptyState>
    </div>
  </div>
</template>

<style scoped>
.nf { text-align: center; padding: 24px 16px; }
.btns { display: flex; gap: 10px; justify-content: center; margin-top: 4px; }
</style>
