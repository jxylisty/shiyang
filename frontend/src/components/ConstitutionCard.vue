<script setup>
/**
 * 体质名片分享海报（T2-10）：Canvas 绘制 → 下载 PNG
 * 内容：主体质+兼夹、体质一句画像、宜吃/少碰、本周打卡数、品牌与二维码
 * 数据：Me 页已有的最新档案 record + 周打卡数（调用方传入，缺省容错）
 */
import { ref, watch } from 'vue'
import QRCode from 'qrcode'

const props = defineProps({
  show: Boolean,
  record: { type: Object, default: null },   // 最新体质档案（listRecords[0]）
  weekCount: { type: Number, default: 0 },   // 本周打卡天数
})
const emit = defineEmits(['update:show'])

const url = ref('')
const busy = ref(false)
const failed = ref(false)
const canvasEl = ref(null)

const PORTRAITS = {
  pinghe: '体质均衡，气血调和的「别人家的体质」',
  qixu: '容易累、爱出虚汗，元气需要充电',
  yangxu: '手脚发凉怕冷，身体缺一点「小火炉」',
  yinxu: '口干手心热，身体偏「省水模式」',
  tanshi: '身体沉重痰多，需要「甩掉湿包袱」',
  shire: '面部油腻易生痘，湿与热要双清',
  xueyu: '面色晦暗易瘀斑，气血要「通」',
  qiyu: '情绪低落爱叹气，先把气理顺',
  tebing: '容易过敏打喷嚏，重点是「稳」住屏障',
}

watch(() => props.show, async (open) => {
  if (!open || url.value) return
  busy.value = true; failed.value = false
  try { await draw() } catch { failed.value = true } finally { busy.value = false }
})

async function drawQr(ctx, x, y, size) {
  try {
    const dataUrl = await QRCode.toDataURL(window.location.origin + '/quiz', {
      width: 240, margin: 1, color: { dark: '#1d4a38', light: '#ffffff' },
    })
    const img = new Image()
    await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = dataUrl })
    ctx.fillStyle = '#fff'
    ctx.fillRect(x - 6, y - 6, size + 12, size + 12)
    ctx.drawImage(img, x, y, size, size)
  } catch { /* 二维码失败不影响海报 */ }
}

async function draw() {
  const r = props.record
  const W = 750, H = 1000
  const c = canvasEl.value
  if (!c) return
  c.width = W; c.height = H
  const ctx = c.getContext('2d')
  // 背景
  const g = ctx.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, '#359068'); g.addColorStop(1, '#1d4a38')
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H)
  ctx.fillStyle = 'rgba(255,255,255,0.06)'
  ctx.beginPath(); ctx.arc(640, 140, 190, 0, 7); ctx.fill()
  ctx.beginPath(); ctx.arc(90, 880, 150, 0, 7); ctx.fill()

  // 标题
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'
  ctx.font = 'bold 28px "PingFang SC","Microsoft YaHei",sans-serif'
  ctx.fillText('我的体质名片', W / 2, 108)

  // 主体质大字
  const mainName = r?.main_name || '平和质'
  ctx.font = 'bold 76px "PingFang SC","Microsoft YaHei",sans-serif'
  ctx.fillText(mainName, W / 2, 220)
  ctx.font = '16px sans-serif'; ctx.fillStyle = 'rgba(255,255,255,0.8)'
  const portrait = PORTRAITS[r?.main_code] || PORTRAITS.pinghe
  ctx.fillText(portrait, W / 2, 258)
  // 兼夹
  const combined = (r?.combined || []).filter(x => x !== mainName)
  if (combined.length) {
    ctx.fillStyle = 'rgba(255,255,255,0.95)'
    ctx.font = 'bold 15px sans-serif'
    ctx.fillText(`兼夹：${combined.slice(0, 3).join(' · ')}`, W / 2, 288)
  }

  // 白卡：宜/忌 + 本周
  ctx.fillStyle = '#fff'
  roundRect(ctx, 50, 330, W - 100, 500, 24); ctx.fill()
  ctx.textAlign = 'left'
  ctx.fillStyle = '#1f2b26'; ctx.font = 'bold 22px sans-serif'
  ctx.fillText('本周食养', 90, 385)
  ctx.font = '15px sans-serif'; ctx.fillStyle = '#55645d'
  ctx.fillText(`打卡 ${props.weekCount} 天 · 持续记录体质变化`, 90, 418)

  ctx.fillStyle = '#1f2b26'; ctx.font = 'bold 22px sans-serif'
  ctx.fillText('测一测你的体质', 90, 480)
  ctx.font = '14px sans-serif'; ctx.fillStyle = '#64736a'
  wrapLines(ctx, '60 道国家标准题 · 出具成分级食养推荐 · 每个方子都有「成分说明书」', 90, 512, W - 180, 22, 2)

  // 九维小格（若有转化分）
  const tf = r?.transformed
  if (tf && Object.keys(tf).length) {
    const dims = ['pinghe', 'qixu', 'yangxu', 'yinxu', 'tanshi', 'shire', 'xueyu', 'qiyu', 'tebing']
    const labels = ['平和', '气虚', '阳虚', '阴虚', '痰湿', '湿热', '血瘀', '气郁', '特禀']
    const gx = 90, gy = 580, gw = (W - 180 - 8 * 10) / 9, gh = 90
    dims.forEach((d, i) => {
      const v = Math.min(100, tf[d] ?? 0)
      const x = gx + i * (gw + 10)
      ctx.fillStyle = '#f4faf7'
      roundRect(ctx, x, gy, gw, gh, 10); ctx.fill()
      ctx.fillStyle = '#2e7d5b'; ctx.textAlign = 'center'
      ctx.font = 'bold 17px sans-serif'
      ctx.fillText(Math.round(v), x + gw / 2, gy + 38)
      ctx.fillStyle = '#64736a'; ctx.font = '11px sans-serif'
      ctx.fillText(labels[i], x + gw / 2, gy + 62)
    })
    ctx.textAlign = 'left'; ctx.fillStyle = '#64736a'; ctx.font = '12px sans-serif'
    ctx.fillText('转化分（0-100）· 偏颇体质 ≥40 判定为「是」', 90, 705)
  }

  // 品牌 + 二维码
  ctx.textAlign = 'center'
  ctx.fillStyle = '#fff'; ctx.font = 'bold 26px sans-serif'
  ctx.fillText('食养有据', W / 2 - 55, 895)
  ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.font = '13px sans-serif'
  ctx.fillText('药食同源 · 成分有据', W / 2 - 55, 922)
  await drawQr(ctx, W - 185, 850, 115)
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.font = '12px sans-serif'
  ctx.fillText('健康参考信息，不构成医疗建议', W / 2, H - 30)
  url.value = c.toDataURL('image/png')
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, x + w, x + w, y, r)
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
  a.download = `食养有据-体质名片.png`
  a.click()
}
function close() { emit('update:show', false) }
</script>

<template>
  <van-popup :show="show" @update:show="close" position="bottom" round style="max-width:750px;margin:0 auto">
    <div class="poster-wrap">
      <p class="p-title">体质名片</p>
      <canvas ref="canvasEl" style="display:none"></canvas>
      <div v-if="busy" class="p-status"><span class="p-spinner"></span>正在生成名片…</div>
      <div v-else-if="failed" class="p-status shake">生成失败，请关闭后重试</div>
      <template v-else-if="url">
        <img :src="url" class="poster-img" />
        <p class="p-hint">手机端长按图片可保存/转发</p>
      </template>
      <div class="p-btns">
        <button class="btn ghost" @click="close">关闭</button>
        <button class="btn" :disabled="!url" @click="download">保存图片</button>
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.poster-wrap { padding: 16px; }
.p-title { font-weight: 700; text-align: center; margin-bottom: 12px; }
.poster-img { width: 100%; border-radius: 12px; animation: np-in .45s var(--ease-spring); }
@keyframes np-in { from { opacity: 0; scale: 0.94; } }
.p-hint { text-align: center; font-size: 11px; color: var(--ink-400); margin-top: 8px; }
.p-status { text-align: center; color: var(--ink-400); padding: 60px 0; font-size: 14px; }
.p-spinner {
  display: block; width: 22px; height: 22px; margin: 0 auto 10px;
  border: 3px solid var(--green-100); border-top-color: var(--green-600); border-radius: 50%;
  animation: np-spin .8s linear infinite;
}
@keyframes np-spin { to { rotate: 360deg; } }
.p-btns { display: flex; gap: 10px; margin-top: 12px; }
.p-btns .btn { flex: 1; }
</style>
