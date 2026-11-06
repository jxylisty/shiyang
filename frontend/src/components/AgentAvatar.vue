<script setup>
/**
 * 「青囊」食养寻证助手 —— 专属器物灵徽组件（开光青瓷悬壶 + 双灵芽 + 朱砂系结 + 寻证星芒）
 *
 * 设计定位：
 * - 区分于全站左上角的单叶品牌标（食养有据），为 AI 模块建立独立、雅致、可辨识的挑战杯级学术产品形象；
 * - 纯内联矢量 SVG，24px 小徽章至 68px 欢迎主视觉均保持锐利，天然适配宣纸浅底与暗色模式；
 * - 支持三种状态：idle（温润呼吸+自然眨眼）、thinking（本草氤氲+外环寻证脉冲）、speaking（轻点回应）。
 */
const props = defineProps({
  size: { type: [Number, String], default: 32 },
  state: {
    type: String,
    default: 'idle', // 'idle' | 'thinking' | 'speaking'
  },
})

const uid = ++uidCounter
</script>

<script>
let uidCounter = 0
</script>

<template>
  <span
    class="qn-avatar"
    :class="[`is-${props.state}`]"
    :style="{ width: `${props.size}px`, height: `${props.size}px` }"
    role="img"
    aria-label="青囊·食养寻证助手"
  >
    <span v-if="props.state === 'thinking'" class="qn-pulse-ring" aria-hidden="true" />
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      class="qn-svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient :id="`qn-glaze-${uid}`" x1="15" y1="13" x2="33" y2="39" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#69ab8d" />
          <stop offset="48%" stop-color="#35755a" />
          <stop offset="100%" stop-color="#1d4937" />
        </linearGradient>
        <radialGradient :id="`qn-bg-${uid}`" cx="38%" cy="30%" r="70%">
          <stop offset="0%" stop-color="#fcf9f0" />
          <stop offset="100%" stop-color="#e3efe5" />
        </radialGradient>
      </defs>

      <!-- 宣纸青玉外底盘 -->
      <circle cx="24" cy="24" r="22.2" :fill="`url(#qn-bg-${uid})`" class="qn-disc" />
      <circle cx="24" cy="24" r="21.5" stroke="#2a5f4a" stroke-opacity="0.22" stroke-width="1.1" />

      <!-- 思考态氤氲茶雾微粒 -->
      <g v-if="props.state === 'thinking'" class="qn-steam">
        <circle cx="15.2" cy="14.5" r="1.5" fill="#5da383" opacity="0.65" class="qn-vapor v1" />
        <circle cx="13.5" cy="10.5" r="1.05" fill="#cf9338" opacity="0.55" class="qn-vapor v2" />
      </g>

      <!-- 悬壶主体组（呼吸与轻点动效） -->
      <g class="qn-vessel">
        <!-- 壶底浅影 -->
        <ellipse cx="24" cy="39.2" rx="7.2" ry="1.6" fill="#14332a" opacity="0.14" />

        <!-- 壶顶双灵芽 -->
        <g class="qn-sprout">
          <path d="M24 14.4V11.3" stroke="#2a5f4a" stroke-width="1.8" stroke-linecap="round" />
          <path d="M24 12.0C24.5 8.2 28.4 6.6 31.1 7.5C30.0 10.6 26.9 12.3 24 12.0Z" fill="#35755a" />
          <path d="M24 12.4C23.1 9.6 20.2 8.7 18.2 9.5C19.2 11.8 21.7 12.7 24 12.4Z" fill="#6cb28f" />
        </g>

        <!-- 青瓷药葫芦器身 -->
        <path
          d="M21.4 14.2Q24 13.4 26.6 14.2C29.9 14.9 30.9 18.8 28.1 22.0Q27.2 23.0 28.7 24.1C34.0 26.4 34.4 34.0 29.6 37.3Q24 39.7 18.4 37.3C13.6 34.0 14.0 26.4 19.3 24.1Q20.8 23.0 19.9 22.0C17.1 18.8 18.1 14.9 21.4 14.2Z"
          :fill="`url(#qn-glaze-${uid})`"
        />

        <!-- 瓷釉高光弧 -->
        <circle cx="20.7" cy="17.6" r="1.15" fill="#ffffff" fill-opacity="0.48" />
        <path
          d="M17.2 27.4C16.3 29.8 16.7 32.8 18.2 34.6"
          stroke="#ffffff"
          stroke-opacity="0.38"
          stroke-width="1.35"
          stroke-linecap="round"
        />

        <!-- 朱砂束腰绳结 -->
        <path d="M19.8 22.9Q24 24.2 28.2 22.9" stroke="#b3392e" stroke-width="2.15" stroke-linecap="round" />
        <path d="M24.2 23.8L25.7 26.0" stroke="#b3392e" stroke-width="1.25" stroke-linecap="round" />
        <circle cx="24" cy="23.5" r="1.55" fill="#cf4b3d" />

        <!-- 青瓷开光肚窗（承载温润灵眸，保证小尺寸高对比清晰度） -->
        <ellipse cx="24" cy="31.3" rx="6.5" ry="4.65" fill="#fbf7ec" fill-opacity="0.95" />

        <!-- 灵眸与微表情 -->
        <g class="qn-eyes">
          <template v-if="props.state === 'thinking'">
            <!-- 思考寻证态：专注弯眸 -->
            <path d="M20.2 30.9Q21.5 29.5 22.8 30.9" stroke="#183a2e" stroke-width="1.55" stroke-linecap="round" />
            <path d="M25.2 30.9Q26.5 29.5 27.8 30.9" stroke="#183a2e" stroke-width="1.55" stroke-linecap="round" />
          </template>
          <template v-else>
            <circle cx="21.5" cy="30.7" r="1.3" fill="#183a2e" />
            <circle cx="26.5" cy="30.7" r="1.3" fill="#183a2e" />
            <circle cx="21.9" cy="30.3" r="0.42" fill="#ffffff" />
            <circle cx="26.9" cy="30.3" r="0.42" fill="#ffffff" />
          </template>
        </g>
        <!-- 温润浅笑 -->
        <path d="M22.8 33.0Q24 34.0 25.2 33.0" stroke="#2a5f4a" stroke-width="1.25" stroke-linecap="round" />
      </g>

      <!-- 右上角「科学寻证」赭金星芒 -->
      <path
        class="qn-spark"
        d="M35.8 9.6L36.65 12.15L39.2 13.0L36.65 13.85L35.8 16.4L34.95 13.85L32.4 13.0L34.95 12.15Z"
        fill="#c98a2c"
      />
    </svg>
  </span>
</template>

<style scoped>
.qn-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 50%;
  user-select: none;
}

.qn-svg {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}

/* 暗色模式下外底盘柔化压暗，保持青瓷主体温润对比 */
:global(:root:is(.van-theme-dark, [data-theme="dark"])) .qn-disc {
  opacity: 0.9;
}

/* 静候态：轻微悬浮 + 自然眨眼 + 星芒微烁 */
.qn-vessel {
  transform-origin: 24px 30px;
  animation: qnFloat 3.6s ease-in-out infinite;
}
.qn-sprout {
  transform-origin: 24px 14px;
  animation: qnSproutSway 4.2s ease-in-out infinite;
}
.qn-eyes {
  transform-origin: 24px 30.7px;
  animation: qnBlink 4.8s ease-in-out infinite;
}
.qn-spark {
  transform-origin: 35.8px 13px;
  animation: qnSparkle 3.2s ease-in-out infinite;
}

/* 思考寻证态：呼吸加快 + 星芒旋转闪烁 + 外环水波脉冲 */
.qn-avatar.is-thinking .qn-vessel {
  animation: qnThinkBob 1.6s ease-in-out infinite;
}
.qn-avatar.is-thinking .qn-eyes {
  animation: none;
}
.qn-avatar.is-thinking .qn-spark {
  animation: qnSparkSpin 2.2s ease-in-out infinite;
}
.qn-pulse-ring {
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  border: 1.5px solid rgba(58, 122, 94, 0.42);
  pointer-events: none;
  animation: qnRingOut 1.9s cubic-bezier(0.22, 1, 0.36, 1) infinite;
}
.qn-vapor {
  animation: qnSteamUp 1.8s ease-out infinite;
}
.qn-vapor.v2 {
  animation-delay: 0.6s;
}

/* 输出解答态：温和点头韵律 */
.qn-avatar.is-speaking .qn-vessel {
  animation: qnSpeakNod 1.3s ease-in-out infinite;
}

@keyframes qnFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-0.9px); }
}
@keyframes qnSproutSway {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(3.5deg); }
}
@keyframes qnBlink {
  0%, 44%, 48%, 100% { transform: scaleY(1); }
  46% { transform: scaleY(0.12); }
}
@keyframes qnSparkle {
  0%, 100% { transform: scale(0.88); opacity: 0.78; }
  50% { transform: scale(1.12); opacity: 1; }
}
@keyframes qnThinkBob {
  0%, 100% { transform: translateY(0) rotate(-1.5deg); }
  50% { transform: translateY(-1.4px) rotate(1.5deg); }
}
@keyframes qnSparkSpin {
  0%, 100% { transform: scale(0.85) rotate(0deg); opacity: 0.75; }
  50% { transform: scale(1.22) rotate(45deg); opacity: 1; }
}
@keyframes qnRingOut {
  0% { transform: scale(0.88); opacity: 0.8; }
  100% { transform: scale(1.24); opacity: 0; }
}
@keyframes qnSteamUp {
  0% { transform: translateY(2px) scale(0.8); opacity: 0; }
  40% { opacity: 0.75; }
  100% { transform: translateY(-5px) scale(1.15); opacity: 0; }
}
@keyframes qnSpeakNod {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-1.1px) scale(1.02); }
}

@media (prefers-reduced-motion: reduce) {
  .qn-vessel,
  .qn-sprout,
  .qn-eyes,
  .qn-spark,
  .qn-pulse-ring,
  .qn-vapor {
    animation: none !important;
  }
}
</style>
