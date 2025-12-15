import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘' }
  },
  {
    path: '/channels',
    name: 'Channels',
    component: () => import('@/views/Channels.vue'),
    meta: { title: '频道管理' }
  },
  {
    path: '/groups',
    name: 'Groups',
    component: () => import('@/views/Groups.vue'),
    meta: { title: '分组管理' }
  },
  {
    path: '/slots',
    name: 'Slots',
    component: () => import('@/views/Slots.vue'),
    meta: { title: '槽位管理' }
  },
  {
    path: '/creatives',
    name: 'Creatives',
    component: () => import('@/views/Creatives.vue'),
    meta: { title: '素材管理' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: '系统设置' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
