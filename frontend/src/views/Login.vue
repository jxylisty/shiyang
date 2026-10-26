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
const errShake = ref(0)              // 递增 key：错误出现时重放 shake

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
    errShake.value++
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
      <!-- 注册昵称字段：高度过渡展开/收起 -->
      <Transition name="field-grow">
        <div class="field" v-if="mode === 'register'">
          <label>昵称（可选）</label>
          <input v-model="nickname" placeholder="怎么称呼你" />
        </div>
      </Transition>

      <p class="err shake" v-if="error" :key="errShake">{{ error }}</p>

      <button class="btn block" :disabled="busy || !username || !password" @click="submit">
        <span v-if="busy" class="spinner"></span>
        {{ busy ? '请稍候…' : (mode === 'login' ? '登录' : '创建账号') }}
      </button>
      <button type="button" class="switch" @click="mode = mode === 'login' ? 'register' : 'login'; error = ''">
        {{ mode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.login-card { max-width: 420px; margin: 40px auto; animation: rise .5s var(--ease-out-soft) backwards; }
.login-card h2 { text-align: center; color: var(--green-700); }
.sub { font-size: 12px; color: var(--ink-400); text-align: center; margin: 4px 0 18px; }
.field { margin-bottom: 14px; overflow: hidden; }
.field label { display: block; font-size: 13px; color: var(--ink-600); margin-bottom: 4px; }
.field input {
  width: 100%; padding: 11px 14px; border: 1px solid var(--green-100); border-radius: 10px;
  font-size: 15px; outline: none; background: #fff;
  transition: border-color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.field input:focus { border-color: var(--green-600); box-shadow: 0 0 0 3px var(--green-50); }
/* 注册昵称字段展开/收起 */
.field-grow-enter-active, .field-grow-leave-active { transition: opacity .25s ease, height .25s var(--ease-out-soft), margin .25s ease; }
.field-grow-enter-from, .field-grow-leave-to { opacity: 0; height: 0 !important; margin-bottom: 0 !important; }
.err { color: var(--red-text); font-size: 13px; margin-bottom: 10px; }
/* spinner 用全局定义（style.css） */
.switch { display: block; text-align: center; font-size: 13px; color: var(--green-700); margin: 14px auto 0; cursor: pointer; background: none; border: none; padding: 0; }
</style>
