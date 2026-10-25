import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/Home.vue'), meta: { title: '食养有据' } },
  { path: '/quiz', name: 'quiz', component: () => import('../views/Quiz.vue'), meta: { title: '体质测评' } },
  { path: '/recipes', name: 'recipes', component: () => import('../views/Recipes.vue'), meta: { title: '方子库' } },
  { path: '/recipes/:id', name: 'recipeDetail', component: () => import('../views/RecipeDetail.vue'), meta: { title: '方子详情' } },
  { path: '/herbs', name: 'herbs', component: () => import('../views/Herbs.vue'), meta: { title: '药材图鉴' } },
  { path: '/compounds', name: 'compounds', component: () => import('../views/Compounds.vue'), meta: { title: '成分库' } },
  { path: '/constitution/:code', name: 'constitution', component: () => import('../views/Constitution.vue'), meta: { title: '体质详情' } },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue'), meta: { title: '登录' } },
  { path: '/me', name: 'me', component: () => import('../views/Me.vue'), meta: { title: '我的' } },
  { path: '/:pathMatch(.*)*', name: 'notFound', component: () => import('../views/NotFound.vue'), meta: { title: '页面不存在' } },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})
