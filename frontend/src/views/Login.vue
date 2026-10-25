<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { login, register, saveSession } from '../api'

const router = useRouter()
const route = useRoute()
const mode = ref('login')            // login | register
const username = ref('')
const password = ref('')
const nickname = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''; busy.value = true
  try {
    const fn = mode.value === 'login' ? login : register
    const { data } = await fn(username.value.trim(), password.value, nickname.value.trim() || undefined)
    saveSession(data.data)
    // 带来源页跳回（如从方子详情页点收藏），无则去「我的」
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    router.push(redirect.startsWith('/') ? redirect : '/me')
  } catch (e) {
    error.value = e?.response?.data?.detail || '操作失败，请重试'
  } finally { busy.value = false }
}
</script>

<template>
  <div class="page">
    <div class="card login-card">
      <h2>{{ mode === 'login' ? '登录' : '注册' }}</h2>
      <p class="sub">登录后可保存体质档案、收藏方子、查看历史对比</p>

      <div class="field">
        <label>用户名</label>
        <input v-model="username" placeholder="3-20位字母数字下划线" autocomplete="username" />
      </div>
      <div class="field">
        <label>密码</label>
        <input v-model="password" type="password" placeholder="至少6位" autocomplete="current-password"
               @keyup.enter="submit" />
      </div>
      <div class="field" v-if="mode === 'register'">
        <label>昵称（可选）</label>
        <input v-model="nickname" placeholder="怎么称呼你" />
      </div>

      <p class="err" v-if="error">{{ error }}</p>

      <button class="btn block" :disabled="busy || !username || !password" @click="submit">
        {{ busy ? '请稍候…' : (mode === 'login' ? '登录' : '创建账号') }}
      </button>
      <p class="switch" @click="mode = mode === 'login' ? 'register' : 'login'; error = ''">
        {{ mode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-card { max-width: 420px; margin: 40px auto; }
.login-card h2 { text-align: center; color: var(--green-700); }
.sub { font-size: 12px; color: var(--ink-400); text-align: center; margin: 4px 0 18px; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 13px; color: var(--ink-600); margin-bottom: 4px; }
.field input {
  width: 100%; padding: 11px 14px; border: 1px solid var(--green-100); border-radius: 10px;
  font-size: 15px; outline: none; background: #fff;
}
.field input:focus { border-color: var(--green-600); }
.err { color: var(--red-500); font-size: 13px; margin-bottom: 10px; }
.switch { text-align: center; font-size: 13px; color: var(--green-700); margin-top: 14px; cursor: pointer; }
</style>
