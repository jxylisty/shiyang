import { ref, watch, onMounted, onUnmounted } from 'vue'

// easeOutCubic 补间时间轴：用 setTimeout(16ms) 驱动而非 rAF——
// rAF 在页面隐藏/截屏场景会被浏览器暂停，数字/条形会永远停在 0（本项目实测踩过）；
// setTimeout 在后台只会被限流但能走完。返回取消句柄，供组件卸载时清理。
export function tween(duration, onFrame) {
  let timer = 0, stopped = false
  const t0 = performance.now()
  const tick = () => {
    if (stopped) return
    const p = Math.min(1, (performance.now() - t0) / duration)
    onFrame(1 - Math.pow(1 - p, 3), p)
    if (p < 1) timer = setTimeout(tick, 16)
  }
  tick()
  return () => { stopped = true; clearTimeout(timer) }
}

// 数字滚动 composable：数值变化时从当前值滚到新值
export function useCountUp(source, duration = 800) {
  const display = ref(0)
  let cancel = null

  function animate(to) {
    if (cancel) cancel()
    const from = display.value
    if (from === to) return
    cancel = tween(duration, (ease) => { display.value = Math.round(from + (to - from) * ease) })
  }

  onMounted(() => {
    if (source.value != null) animate(source.value)
  })
  watch(source, (v) => { if (v != null) animate(v) })
  onUnmounted(() => { if (cancel) cancel() })

  return display
}

// 等本帧提交后的下一拍再给元素终值（条形/进度真正从 0 播起）：
// 双 setTimeout 替代双 rAF——隐藏页签里 rAF 不触发会定格在 0
export const afterPaint = (fn) => setTimeout(() => setTimeout(fn, 16), 16)

// 方向感过渡钩子工厂：Vue <Transition :css="false"> 的 enter/leave 实现。
// 收尾用 setTimeout 而非 transitionend——隐藏页签/切后台时 transitionend 可能永不到达，
// mode="out-in" 下会卡死整页。dir 由 getDir 提供：1 前进（新元素从右入），-1 后退（从左入），0 无方向。
export function makeNavHooks({
  getDir = () => 0,
  enterDx = 32, enterDy = 6, leaveDx = 18,
  enterDur = '.18s', enterDurT = '.22s', enterTotal = 300,
  leaveDur = '.16s', leaveDurT = '.18s', leaveTotal = 200,
} = {}) {
  let timers = []
  const clear = () => { for (const t of timers) clearTimeout(t); timers = [] }

  function enter(el, done) {
    clear()
    const dir = getDir()
    const dx = dir === 1 ? enterDx : (dir === -1 ? -enterDx : 0)
    const dy = dir === 0 ? enterDy : 0
    el.style.opacity = '0'
    el.style.transform = `translate(${dx}px, ${dy}px)`
    // rAF 冻结环境下 50ms 内由 setTimeout 兜底起播
    let started = false
    const start = () => {
      if (started) return
      started = true
      el.style.transition = `opacity ${enterDur} ease, transform ${enterDurT} cubic-bezier(0.22, 1, 0.36, 1)`
      el.style.opacity = '1'
      el.style.transform = 'translate(0, 0)'
    }
    requestAnimationFrame(start)
    timers.push(setTimeout(start, 50))
    timers.push(setTimeout(() => { el.style.transition = ''; el.style.opacity = ''; el.style.transform = ''; done() }, enterTotal))
  }

  function leave(el, done) {
    clear()
    const dir = getDir()
    const dx = dir === 1 ? -leaveDx : (dir === -1 ? leaveDx : 0)
    el.style.transition = `opacity ${leaveDur} ease, transform ${leaveDurT} cubic-bezier(0.22, 1, 0.36, 1)`
    el.style.opacity = '0'
    if (dx) el.style.transform = `translateX(${dx}px)`
    timers.push(setTimeout(done, leaveTotal))
  }

  return { enter, leave, clear }
}
