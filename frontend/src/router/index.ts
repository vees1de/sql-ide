import { createRouter, createWebHistory } from 'vue-router';
import MainLayout from '@/layouts/MainLayout.vue';
import DataView from '@/views/DataView.vue';
import ChatView from '@/views/ChatView.vue';
import NotebookView from '@/views/NotebookView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', redirect: '/chat' },
        { path: 'chat', name: 'chat', component: ChatView },
        { path: 'colab', name: 'colab', component: NotebookView },
        { path: 'notebook', name: 'notebook-home', component: NotebookView },
        { path: 'data', name: 'data', component: DataView },
        { path: 'notebooks/:notebookId', name: 'notebook', component: NotebookView }
      ]
    }
  ]
});

export default router;
