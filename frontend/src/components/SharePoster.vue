<script setup>
// 分享海报：Canvas 绘制 → 下载 PNG（纯前端，无服务端依赖）
// 打开弹层时才拉取配方并懒绘制，避免进详情页就白跑一次请求
// P2：右下角加站点二维码（qrcode 包本地生成 dataURL，扫码直达当前站点）
import { ref, watch } from 'vue'
import QRCode from 'qrcode'
import { getRecipe } from '../api'

const props = defineProps({ recipeId: [String, Number] })
const show = ref(false)
const canvasEl = ref(null)
const url = ref('')
const recipeName = ref('')
const busy = ref(false)
const failed = ref(false)

watch(show, async (open) => {
  if (!open || url.value) return
  busy.value = true; failed.value = false
  try {
    const { data } = await getRecipe(props.recipeId)
    recipeName.value = data.data.name || ''
    await draw(data.data)
  } catch {
    failed.value = true
  } finally { busy.value = false }
})

async function drawQr(ctx, x, y, size) {
  try {
    const dataUrl = await QRCode.toDataURL(window.location.origin, {
      width: 240, margin: 1, color: { dark: '#1d4a38', light: '#ffffff' },
    })
    const img = new Image()
    await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = dataUrl })
    // 白底圆角托底，再贴二维码
    ctx.fillStyle = '#fff'
    ctx.fillRect(x - 8, y - 8, size + 16, size + 16)
    ctx.drawImage(img, x, y, size, size)
  } catch { /* 二维码失败不影响海报其余部分 */ }
}

async function draw(r) {
  const W = 750, H = 1000
  const c = canvasEl.value
  if (!c) return
  c.width = W; c.height = H
  const ctx = c.getContext('2d')
  // 背景
  const g = ctx.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, '#2e7d5b'); g.addColorStop(1, '#1d4a38')
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H)
  // 装饰圆
  ctx.fillStyle = 'rgba(255,255,255,0.06)'
  ctx.beginPath(); ctx.arc(650, 120, 180, 0, 7); ctx.fill()
  ctx.beginPath(); ctx.arc(80, 900, 140, 0, 7); ctx.fill()
  // 标题区
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'
  ctx.font = 'bold 30px "PingFang SC","Microsoft YaHei",sans-serif'
  ctx.fillText(r.name.slice(0, 14), W / 2, 120)
  ctx.font = '16px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.fillText((r.oneliner || '').slice(0, 22), W / 2, 156)
  // 白卡
  ctx.fillStyle = '#fff'
  roundRect(ctx, 50, 200, W - 100, 640, 24); ctx.fill()
  // 配方
  ctx.fillStyle = '#1f2b26'; ctx.textAlign = 'left'
  ctx.font = 'bold 22px sans-serif'
  ctx.fillText('配方', 90, 250)
  ctx.font = '15px sans-serif'; ctx.fillStyle = '#55645d'
  const mats = r.materials.slice(0, 8).map(m => `${m.name}${m.grams ? m.grams + 'g' : '适量'}`)
  wrapLines(ctx, mats.join(' · '), 90, 284, W - 180, 26, 2)
  // 成分亮点
  if (r.analysis) {
    ctx.fillStyle = '#1f2b26'; ctx.font = 'bold 22px sans-serif'
    ctx.fillText('成分亮点', 90, 380)
    ctx.font = '15px sans-serif'; ctx.fillStyle = '#2e7d5b'
    r.analysis.top_compounds.slice(0, 4).forEach((cp, i) => {
      ctx.fillText(`· ${cp.name.slice(0, 16)}  入血概率 ${cp.prob_cctcm}`, 90, 416 + i * 30)
    })
    const rs = r.analysis.radar_summary || {}
    ctx.fillStyle = '#8a978f'; ctx.font = '13px sans-serif'
    ctx.fillText(`三维参考：抗炎 ${Math.round(rs.anti_inflammatory || 0)} / 免疫 ${Math.round(rs.immune_regulation || 0)} / 气道 ${Math.round(rs.airway_repair || 0)}`, 90, 550)
  }
  // 出处与品牌
  ctx.fillStyle = '#8a978f'; ctx.font = '13px sans-serif'
  wrapLines(ctx, `来源：${(r.source || '').slice(0, 40)}`, 90, 600, W - 180, 20, 2)
  ctx.textAlign = 'center'
  ctx.fillStyle = '#2e7d5b'; ctx.font = 'bold 26px sans-serif'
  ctx.fillText('食养有据', W / 2 - 60, 780)
  ctx.fillStyle = '#8a978f'; ctx.font = '13px sans-serif'
  ctx.fillText('每个方子，都有一份成分说明书', W / 2 - 60, 810)
  // 右下角二维码（扫码直达站点）
  await drawQr(ctx, W - 190, 720, 130)
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.font = '12px sans-serif'
  ctx.fillText('健康参考信息，不构成医疗建议', W / 2, H - 36)
  url.value = c.toDataURL('image/png')
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}
function wrapLines(ctx, text, x, y, maxW, lh, maxLines) {
  let line = '', n = 0
  for (const ch of text) {
    if (ctx.measureText(line + ch).width > maxW) {
      ctx.fillText(line, x, y + n * lh); n++; line = ch
      if (n >= maxLines) { ctx.fillText(line + '…', x, y + n * lh); return }
    } else line += ch
  }
  if (line) ctx.fillText(line, x, y + n * lh)
}
function download() {
  const a = document.createElement('a')
  a.href = url.value
  a.download = `食养有据-${recipeName.value || props.recipeId}.png`
  a.click()
}
</script>

<template>
  <van-popup v-model:show="show" position="bottom" round style="max-width:750px;margin:0 auto">
    <div class="poster-wrap">
      <p class="p-title">分享海报</p>
      <canvas ref="canvasEl" style="display:none"></canvas>
      <div v-if="busy" class="p-status">正在生成…</div>
      <div v-else-if="failed" class="p-status">生成失败，请关闭后重试</div>
      <img v-else-if="url" :src="url" class="poster-img" />
      <div class="p-btns">
        <button class="btn ghost" @click="show = false">关闭</button>
        <button class="btn" :disabled="!url" @click="download">保存图片</button>
      </div>
    </div>
  </van-popup>
  <button class="btn ghost" @click="show = true">生成分享海报</button>
</template>

<style scoped>
.poster-wrap { padding: 16px; }
.p-title { font-weight: 700; text-align: center; margin-bottom: 12px; }
.poster-img { width: 100%; border-radius: 12px; }
.p-status { text-align: center; color: var(--ink-400); padding: 60px 0; font-size: 14px; }
.p-btns { display: flex; gap: 10px; margin-top: 12px; }
.p-btns .btn { flex: 1; }
</style>
