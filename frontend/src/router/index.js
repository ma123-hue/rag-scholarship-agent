import { createRouter, createWebHistory } from 'vue-router'

import AuthView from '../views/AuthView.vue'
import AdminFilesView from '../views/AdminFilesView.vue'
import ChatView from '../views/ChatView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: AuthView,
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      name: 'chat',
      component: ChatView,
      meta: { requiresAuth: true },
    },
    {
      path: '/admin/files',
      name: 'admin-files',
      component: AdminFilesView,
      meta: { requiresAuth: true, requiresAdmin: true },
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('scholar_token')
  const isAdmin = localStorage.getItem('scholar_is_admin') === 'true'
  if (to.meta.requiresAuth && !token) {
    return '/login'
  }
  if (to.meta.requiresAdmin && !isAdmin) {
    return '/'
  }
  if (to.path === '/login' && token) {
    return '/'
  }
  return true
})

export default router
