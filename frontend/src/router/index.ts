import { createRouter, createWebHistory } from 'vue-router';
import MainLayout from '@/layouts/MainLayout.vue';
import DataView from '@/views/DataView.vue';
import ChatView from '@/views/ChatView.vue';
import NotebookView from '@/views/NotebookView.vue';
import WidgetsListView from '@/views/WidgetsListView.vue';
import WidgetView from '@/views/WidgetView.vue';
import DashboardsListView from '@/views/DashboardsListView.vue';
import DashboardBuilderView from '@/views/DashboardBuilderView.vue';
import DashboardView from '@/views/DashboardView.vue';

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
        { path: 'notebooks/:notebookId', name: 'notebook', component: NotebookView },
        { path: 'widgets', name: 'widgets', component: WidgetsListView },
        { path: 'widget/:id', name: 'widget', component: WidgetView },
        { path: 'dashboards', name: 'dashboards', component: DashboardsListView },
        { path: 'dashboards/new', name: 'dashboard-new', component: DashboardBuilderView },
        { path: 'dashboards/:id', name: 'dashboard', component: DashboardView }
      ]
    }
  ]
});

export default router;
