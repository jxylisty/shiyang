import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    // Vant 组件与样式按需自动导入（模板里直接写 <van-xxx />）
    Components({ resolvers: [VantResolver()] }),
  ],
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8100', changeOrigin: true },
    },
  },
})
