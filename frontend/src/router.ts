import { createRouter, createWebHistory } from 'vue-router'

// /l/{code} is the public list URL the API hands out (`public_url`). In production nginx
// serves this app for it; /api/, /r/ and /healthz go to Django.
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./views/HomeView.vue') },
    {
      path: '/l/:code',
      name: 'list',
      component: () => import('./views/ListView.vue'),
      props: true,
    },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('./views/NotFoundView.vue') },
  ],
})
