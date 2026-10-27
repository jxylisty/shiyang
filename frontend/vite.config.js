import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig(({ mode }) => {
  // APP 构建模式：产物内置进 5+App 包，用相对路径 + hash 路由（file:// 下 history 会 404）。
  // web 模式保持原有根路径绝对路径部署行为不变。
  const isApp = mode === 'app'
  return {
    base: isApp ? './' : '/',
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
      host: true, // 监听 0.0.0.0，真机/其他设备可通过局域网 IP 访问
      proxy: {
        '/api': { target: 'http://127.0.0.1:8100', changeOrigin: true },
      },
    },
    build: {
      outDir: isApp ? 'dist-app' : 'dist',
    },
  }
})
