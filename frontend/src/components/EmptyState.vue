<script setup>
// 治愈系空状态：茶杯 + 上升蒸汽 + 轻摆叶片，替代 van-empty 默认图（不引 lottie）
defineProps({
  text: { type: String, default: '这里空空如也' },
})
</script>

<template>
  <div class="empty-motion">
    <div class="cup-wrap" aria-hidden="true">
      <span class="leaf l1">🌿</span>
      <span class="leaf l2">🍃</span>
      <div class="cup">
        <span class="steam s1"></span>
        <span class="steam s2"></span>
        <span class="steam s3"></span>
      </div>
      <div class="saucer"></div>
    </div>
    <p class="e-text">{{ text }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty-motion { text-align: center; padding: 40px 0 32px; }
.cup-wrap { position: relative; display: inline-block; }
.cup {
  position: relative; width: 64px; height: 44px; margin: 0 auto;
  border: 3px solid var(--green-600); border-radius: 8px 8px 26px 26px;
  border-top-width: 0;
}
.cup::before {
  content: ""; position: absolute; right: -16px; top: 6px;
  width: 16px; height: 20px; border: 3px solid var(--green-600);
  border-left: none; border-radius: 0 12px 12px 0;
}
.steam {
  position: absolute; top: -22px; width: 5px; height: 14px; border-radius: 5px;
  background: var(--green-600); opacity: 0; filter: blur(1px);
  animation: steam 2.6s ease-in-out infinite;
}
.s1 { left: 16px; animation-delay: 0s; }
.s2 { left: 30px; animation-delay: 0.9s; }
.s3 { left: 44px; animation-delay: 1.7s; }
.saucer {
  width: 84px; height: 8px; margin: 2px auto 0;
  background: var(--green-100); border-radius: 6px;
}
.leaf { position: absolute; font-size: 16px; opacity: .8; display: inline-block; animation: sway 3.4s ease-in-out infinite; transform-origin: bottom center; }
.l1 { top: -14px; left: -22px; }
.l2 { top: 8px; right: -24px; animation-delay: 1.2s; }
.e-text { margin-top: 14px; color: var(--ink-400); font-size: 13px; }
@media (prefers-reduced-motion: reduce) {
  .steam, .leaf { animation: none; }
  .steam { opacity: .3; }
}
</style>
