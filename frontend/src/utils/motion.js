import { ref, watch, onMounted } from 'vue'

// 数字滚动 composable：rAF + easeOutCubic，数值变化时从当前值滚到新值
// 用 rAF 而非 setTimeout 循环，页面后台时自动暂停不空转
export function useCountUp(source, duration = 800) {
  const display = ref(0)
  let raf = 0

  function animate(to) {
    cancelAnimationFrame(raf)
    const from = display.value
    if (from === to) return
    const t0 = performance.now()
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / duration)
      const ease = 1 - Math.pow(1 - p, 3)
      display.value = Math.round(from + (to - from) * ease)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
  }

  onMounted(() => {
    if (source.value != null) animate(source.value)
  })
  watch(source, (v) => { if (v != null) animate(v) })

  return display
}
