<script setup>
// 周期报告分享海报：Canvas 绘制 → 下载 PNG（数据由 Report.vue 整理成 props 传入）
// 复用 SharePoster 的绘制风格（品牌绿渐变 + 白卡 + 二维码），打通报告的传播链路
import { ref, watch, onMounted, onUnmounted } from 'vue'
import QRCode from 'qrcode'

const props = defineProps({
  show: Boolean,
  report: Object,   // { days, checkin_days, streak, recipes_tried, compounds_covered, targets_covered, hi_blood_covered, top_targets, scenes_hist }
})

const canvasEl = ref(null)
const url = ref('')
const busy = ref(false)
const failed = ref(false)

// 宽屏居中弹窗，窄屏底部抽屉（同 SharePoster 口径）
const mqWide = window.matchMedia('(min-width: 720px)')
const isWide = ref(mqWide.matches)
const onMq = (e) => { isWide.value = e.matches }
onMounted(() => mqWide.addEventListener('change', onMq))
onUnmounted(() => mqWide.removeEventListener('change', onMq))

watch(() => props.show, async (open) => {
  if (!open || url.value || !props.report) return
  busy.value = true; failed.value = false
  try { await draw(props.report) } catch { failed.value = true } finally { busy.value = false }
})

async function drawQr(ctx, x, y, size) {
  try {
    const dataUrl = await QRCode.toDataURL(window.location.origin, {
      width: 240, margin: 1, color: { dark: '#1d4a38', light: '#ffffff' },
    })
    const img = new Image()
    await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = dataUrl })
    ctx.fillStyle = '#fff'
    ctx.fillRect(x - 8, y - 8, size + 16, size + 16)
    ctx.drawImage(img, x, y, size, size)
  } catch { /* 二维码失败不影响海报其余部分 */ }
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

async function draw(r) {
  const W = 750, H = 1200
  const c = canvasEl.value
  if (!c) return
  c.width = W; c.height = H
  const ctx = c.getContext('2d')
  // 背景
  const g = ctx.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, '#2e7d5b'); g.addColorStop(1, '#1d4a38')
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H)
  ctx.fillStyle = 'rgba(255,255,255,0.06)'
  ctx.beginPath(); ctx.arc(650, 120, 180, 0, 7); ctx.fill()
  ctx.beginPath(); ctx.arc(80, 1050, 140, 0, 7); ctx.fill()
  // 标题
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'
  ctx.font = 'bold 34px "PingFang SC","Microsoft YaHei",sans-serif'
  ctx.fillText(`我的 ${r.days} 天食养报告`, W / 2, 110)
  ctx.font = '15px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.fillText('成分有据 · 喝进去的每一口都算数', W / 2, 146)

  // 白卡：概览数字
  ctx.fillStyle = '#fff'
  roundRect(ctx, 50, 190, W - 100, 240, 24); ctx.fill()
  const nums = [
    [r.checkin_days, '打卡天数'], [r.streak, '连续天数'], [r.recipes_tried, '喝过方子'],
    [r.compounds_covered, '覆盖成分'], [r.targets_covered, '覆盖靶点'],
  ]
  ctx.textAlign = 'center'
  nums.forEach(([v, label], i) => {
    const x = 50 + (W - 100) / 10 * (i * 2 + 1)
    ctx.fillStyle = '#2e7d5b'; ctx.font = 'bold 40px sans-serif'
    ctx.fillText(String(v ?? 0), x, 290)
    ctx.fillStyle = '#64736a'; ctx.font = '13px sans-serif'
    ctx.fillText(label, x, 322)
  })
  ctx.fillStyle = '#55645d'; ctx.font = '13px sans-serif'
  const hi = (r.hi_blood_covered || []).length
  ctx.fillText(`其中高入血概率（≥70%）成分 ${hi} 个`, W / 2, 400)

  // 白卡：高频靶点
  let y = 470
  ctx.fillStyle = '#fff'
  roundRect(ctx, 50, y, W - 100, 320, 24); ctx.fill()
  ctx.textAlign = 'left'
  ctx.fillStyle = '#1f2b26'; ctx.font = 'bold 22px sans-serif'
  ctx.fillText('高频关联靶点', 90, y + 44)
  const targets = (r.top_targets || []).slice(0, 5)
  if (targets.length) {
    const maxHits = Math.max(...targets.map(t => t.hits), 1)
    targets.forEach((t, i) => {
      const ty = y + 84 + i * 44
      ctx.fillStyle = '#55645d'; ctx.font = '14px ui-monospace, monospace'
      ctx.fillText(t.gene, 90, ty + 6)
      // 迷你条
      const bx = 240, bw = 380
      ctx.fillStyle = '#e8f4ee'
      roundRect(ctx, bx, ty - 6, bw, 14, 7); ctx.fill()
      ctx.fillStyle = '#2e7d5b'
      roundRect(ctx, bx, ty - 6, Math.max(14, bw * t.hits / maxHits), 14, 7); ctx.fill()
      ctx.fillStyle = '#64736a'; ctx.font = '13px sans-serif'
      ctx.fillText(`${t.hits} 次`, bx + bw + 14, ty + 6)
    })
  } else {
    ctx.fillStyle = '#64736a'; ctx.font = '14px sans-serif'
    ctx.fillText('暂无靶点数据', 90, y + 90)
  }

  // 白卡：场景分布
  y = 830
  ctx.fillStyle = '#fff'
  roundRect(ctx, 50, y, W - 100, 140, 24); ctx.fill()
  ctx.fillStyle = '#1f2b26'; ctx.font = 'bold 22px sans-serif'
  ctx.fillText('场景分布', 90, y + 42)
  const scenes = (r.scenes_hist || []).slice(0, 4)
  if (scenes.length) {
    ctx.font = '14px sans-serif'
    let sx = 90
    scenes.forEach(([s, n]) => {
      const label = `${s} ×${n}`
      const w = ctx.measureText(label).width + 28
      ctx.fillStyle = '#e8f4ee'
      roundRect(ctx, sx, y + 64, w, 34, 17); ctx.fill()
      ctx.fillStyle = '#2e7d5b'
      ctx.fillText(label, sx + 14, y + 86)
      sx += w + 12
      if (sx > W - 220) return
    })
  } else {
    ctx.fillStyle = '#64736a'; ctx.font = '14px sans-serif'
    ctx.fillText('暂无记录', 90, y + 86)
  }

  // 品牌 + 二维码
  ctx.textAlign = 'center'
  ctx.fillStyle = '#fff'; ctx.font = 'bold 26px sans-serif'
  ctx.fillText('食养有据', W / 2 - 60, 1060)
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.font = '13px sans-serif'
  ctx.fillText('每个方子，都有一份成分说明书', W / 2 - 60, 1090)
  await drawQr(ctx, W - 190, 1010, 130)
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.font = '12px sans-serif'
  ctx.fillText('健康参考信息，不构成医疗建议', W / 2, H - 36)
  url.value = c.toDataURL('image/png')
}

function download() {
  const a = document.createElement('a')
  a.href = url.value
  a.download = `食养有据-我的${props.report?.days || ''}天食养报告.png`
  a.click()
}
function onPopupClose(v) { if (!v) emit('update:show', false) }
const emit = defineEmits(['update:show'])
</script>

<template>
  <van-popup :show="show" @update:show="onPopupClose" :position="isWide ? 'center' : 'bottom'" round :class="{ 'wide-popup': isWide }">
    <div class="poster-wrap">
      <p class="p-title">分享我的食养报告</p>
      <canvas ref="canvasEl" style="display:none"></canvas>
      <div v-if="busy" class="p-status">
        <span class="p-spinner"></span>
        正在生成海报…
      </div>
      <div v-else-if="failed" class="p-status shake">生成失败，请关闭后重试</div>
      <template v-else-if="url">
        <img :src="url" class="poster-img" />
        <p class="p-hint">手机端也可长按图片保存</p>
      </template>
      <div class="p-btns">
        <button class="btn ghost" @click="emit('update:show', false)">关闭</button>
        <button class="btn" :disabled="!url" @click="download">保存图片</button>
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.poster-wrap { padding: 16px; }
.p-title { font-weight: 700; text-align: center; margin-bottom: 12px; }
.poster-img { width: 100%; border-radius: 12px; animation: poster-in .45s var(--ease-spring); }
@keyframes poster-in { from { opacity: 0; scale: 0.94; } }
.p-hint { text-align: center; font-size: 11px; color: var(--ink-400); margin-top: 8px; }
.p-status { text-align: center; color: var(--ink-400); padding: 60px 0; font-size: 14px; }
.p-spinner {
  display: block; width: 22px; height: 22px; margin: 0 auto 10px;
  border: 3px solid var(--green-100); border-top-color: var(--green-600); border-radius: 50%;
  animation: p-spin .8s linear infinite;
}
@keyframes p-spin { to { rotate: 360deg; } }
.p-btns { display: flex; gap: 10px; margin-top: 12px; }
.p-btns .btn { flex: 1; }
.wide-popup { width: min(750px, 90vw); }
</style>
