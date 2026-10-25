import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/Home.vue'), meta: { title: '食养有据', depth: 0 } },
  { path: '/quiz', name: 'quiz', component: () => import('../views/Quiz.vue'), meta: { title: '体质测评', depth: 1 } },
  { path: '/recipes', name: 'recipes', component: () => import('../views/Recipes.vue'), meta: { title: '方子库', depth: 1 } },
  { path: '/recipes/compare', name: 'compareLab', component: () => import('../views/CompareLab.vue'), meta: { title: '对比实验室', depth: 2 } },
  { path: '/pantry', name: 'pantry', component: () => import('../views/Pantry.vue'), meta: { title: '我的茶罐', depth: 1 } },
  { path: '/recipes/:id(\\d+)', name: 'recipeDetail', component: () => import('../views/RecipeDetail.vue'), meta: { title: '方子详情', depth: 2 } },
  { path: '/herbs', name: 'herbs', component: () => import('../views/Herbs.vue'), meta: { title: '药材图鉴', depth: 1 } },
  { path: '/compounds', name: 'compounds', component: () => import('../views/Compounds.vue'), meta: { title: '成分库', depth: 1 } },
  { path: '/constitution/:code', name: 'constitution', component: () => import('../views/Constitution.vue'), meta: { title: '体质详情', depth: 2 } },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue'), meta: { title: '登录', depth: 1 } },
  { path: '/me', name: 'me', component: () => import('../views/Me.vue'), meta: { title: '我的', depth: 1 } },
  { path: '/:pathMatch(.*)*', name: 'notFound', component: () => import('../views/NotFound.vue'), meta: { title: '页面不存在', depth: 9 } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// 路由方向感：记录 depth 变化，供 App.vue 的 View Transition 决定滑入/滑出方向
router._navDir = 0
router.beforeEach((to, from) => {
  if (from.name === undefined) { router._navDir = 0; return }  // 首次进入不做方向过渡
  router._navDir = (to.meta.depth ?? 1) >= (from.meta.depth ?? 1) ? 1 : -1
})
export default router
