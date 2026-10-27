import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    // Vant 组件按需自动导入（模板里直接写 <van-xxx />）。
    // importStyle: false —— 样式已由 main.js 全量引入 vant/lib/index.css；
    // 若再让 resolver 按组件注入，各路由 chunk 会多一份 Vant CSS 且后加载，
    // `.van-popup{background:白}` 与 `.van-toast{background:黑}` 同为单类特异性，
    // 后者被覆盖 → toast 变白底白字（已实测复现）。
    Components({ resolvers: [VantResolver({ importStyle: false })] }),
  ],
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8100', changeOrigin: true },
    },
  },
})
