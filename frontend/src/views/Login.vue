<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showSuccessToast } from 'vant'
import { login, register, saveSession } from '../api'
import { getPendingClaimRecord, claimGuestConstitutionIfNeeded } from '../utils/guestArchive'

const router = useRouter()
const route = useRoute()
const mode = ref('login')            // login | register
const username = ref('')
const password = ref('')
const nickname = ref('')
const error = ref('')
const busy = ref(false)
const errShake = ref(0)              // 递增 key：错误出现时重放 shake

const pendingClaim = ref(getPendingClaimRecord())
const safeRedirect = computed(() => {
  const r = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  return r.startsWith('/') && !r.startsWith('/login') ? r : ''
})

async function submit() {
  error.value = ''; busy.value = true
  try {
    const fn = mode.value === 'login' ? login : register
    const { data } = await fn(username.value.trim(), password.value, nickname.value.trim() || undefined)
    saveSession(data.data)
    // 若未登录时已在本机做过 67 题体质测评，自动同步进云端档案，免重测
    const claimed = await claimGuestConstitutionIfNeeded()
    if (claimed) showSuccessToast(`已同步本机测评（${claimed.main_name}）`)
    router.push(safeRedirect.value || '/me')
  } catch (e) {
    error.value = e?.response?.data?.detail || '操作失败，请重试'
    errShake.value++
  } finally { busy.value = false }
}

function skipLogin() {
  router.push(safeRedirect.value || '/')
}
</script>

<template>
  <div class="page">
    <div class="card login-card">
      <h2>{{ mode === 'login' ? '登录' : '创建账号' }}</h2>
      <p class="sub">跨设备同步体质档案、管理家人共养、记录饮用打卡与周期报告</p>

      <div v-if="pendingClaim" class="claim-banner">
        检测到本机已有测评结果（<b>{{ pendingClaim.main_name }}</b>），{{ mode === 'login' ? '登录' : '注册' }}后将自动归入账号档案
      </div>

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

      <div class="guest-foot">
        <span class="guest-note">方子检索、成分溯源、茶罐配伍与体质测评均支持免登录使用</span>
        <button type="button" class="guest-skip" @click="skipLogin">
          {{ safeRedirect ? '暂不登录，返回刚才页面 →' : '先不登录，免密直接体验 →' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-card { max-width: 420px; margin: 32px auto; animation: rise .5s var(--ease-out-soft) backwards; }
.login-card h2 { font-family: var(--font-serif); text-align: center; color: var(--green-text); letter-spacing: 0.04em; }
.sub { font-size: 12px; color: var(--ink-400); text-align: center; margin: 5px 0 16px; line-height: 1.5; }
.claim-banner {
  margin-bottom: 14px; padding: 9px 12px; border-radius: 9px;
  background: var(--green-50); border: 1px solid var(--green-100);
  font-size: 12px; color: var(--ink-600); line-height: 1.55;
}
.claim-banner b { color: var(--green-text); }
.field { margin-bottom: 14px; overflow: hidden; }
.field label { display: block; font-size: 13px; color: var(--ink-600); margin-bottom: 4px; }
.field input {
  width: 100%; padding: 11px 14px; border: 1px solid var(--green-100); border-radius: 10px;
  font-size: 15px; outline: none; background: var(--card); color: var(--ink-900);
  transition: border-color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
}
.field input:focus { border-color: var(--green-600); box-shadow: 0 0 0 3px var(--green-50); }
/* 注册昵称字段展开/收起 */
.field-grow-enter-active, .field-grow-leave-active { transition: opacity .25s ease, height .25s var(--ease-out-soft), margin .25s ease; }
.field-grow-enter-from, .field-grow-leave-to { opacity: 0; height: 0 !important; margin-bottom: 0 !important; }
.err { color: var(--red-text); font-size: 13px; margin-bottom: 10px; }
/* spinner 用全局定义（style.css） */
.switch { display: block; text-align: center; font-size: 13px; color: var(--green-text); margin: 14px auto 0; cursor: pointer; background: none; border: none; padding: 0; }
.guest-foot {
  margin-top: 18px; padding-top: 14px;
  border-top: 1px dashed var(--card-border);
  text-align: center;
}
.guest-note { display: block; font-size: 11.5px; color: var(--ink-400); line-height: 1.5; margin-bottom: 8px; }
.guest-skip {
  background: none; border: none; cursor: pointer; padding: 4px 8px;
  font-size: 13px; font-weight: 600; color: var(--ink-600); font-family: inherit;
  transition: color var(--dur-fast) ease;
}
.guest-skip:hover { color: var(--green-text); }
</style>
