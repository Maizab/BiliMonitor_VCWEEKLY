import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: App,
    props: { uploaderMid: null, bvid: null },
  },
  {
    path: '/:mid(\\d+)',
    name: 'uploader',
    component: App,
    props: (route) => ({ uploaderMid: Number(route.params.mid), bvid: null }),
  },
  {
    path: '/:mid(\\d+)/:bvid',
    name: 'video',
    component: App,
    props: (route) => ({ uploaderMid: Number(route.params.mid), bvid: route.params.bvid }),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
