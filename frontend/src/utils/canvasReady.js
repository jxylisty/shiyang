/**
 * 等待 canvas 元素真正进入 DOM 后再绘制。
 *
 * 背景：van-popup 默认 lazyRender，`show` 变 true 的同一拍内容才挂载；
 * 在 watch 回调里同步读 `canvasEl.value` 会拿到 null，绘制函数静默 return，
 * 弹层就停在「正在生成」或空白。nextTick 之后通常已就绪，但 teleport +
 * 过渡动画下不保证，所以再按 setTimeout 轮询几拍兜底。
 *
 * 不用 requestAnimationFrame：后台标签页 rAF 会被冻结（AGENTS.md §5.4）。
 */
export async function waitForCanvas(elRef, timeoutMs = 600) {
  const started = Date.now()
  // 先让 Vue 完成本次更新（弹层内容挂载）
  await new Promise((resolve) => setTimeout(resolve, 0))
  while (Date.now() - started < timeoutMs) {
    if (elRef.value) return elRef.value
    await new Promise((resolve) => setTimeout(resolve, 16))
  }
  return elRef.value || null
}
