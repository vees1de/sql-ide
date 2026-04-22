import { createRouter, createWebHistory, type RouteLocationRaw } from 'vue-router';
import MainLayout from '@/layouts/MainLayout.vue';
import DataView from '@/views/DataView.vue';
import ChatView from '@/views/ChatView.vue';
import NotebookView from '@/views/NotebookView.vue';
import WidgetsListView from '@/views/WidgetsListView.vue';
import WidgetView from '@/views/WidgetView.vue';
import DashboardsListView from '@/views/DashboardsListView.vue';
import DashboardBuilderView from '@/views/DashboardBuilderView.vue';
import DashboardView from '@/views/DashboardView.vue';

type ViewTransitionScope = 'page' | 'section';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', redirect: '/chat' },
        {
          path: 'chat',
          name: 'chat',
          component: ChatView,
          meta: { viewTransitionScope: 'section' satisfies ViewTransitionScope },
        },
        { path: 'colab', name: 'colab', component: NotebookView },
        { path: 'notebook', name: 'notebook-home', component: NotebookView },
        {
          path: 'data',
          name: 'data',
          component: DataView,
          meta: { viewTransitionScope: 'section' satisfies ViewTransitionScope },
        },
        { path: 'notebooks/:notebookId', name: 'notebook', component: NotebookView },
        { path: 'widgets', name: 'widgets', component: WidgetsListView },
        { path: 'widget/:id', name: 'widget', component: WidgetView },
        {
          path: 'dashboards',
          name: 'dashboards',
          component: DashboardsListView,
          meta: { viewTransitionScope: 'section' satisfies ViewTransitionScope },
        },
        { path: 'dashboards/new', name: 'dashboard-new', component: DashboardBuilderView },
        {
          path: 'dashboards/:id',
          name: 'dashboard',
          component: DashboardView,
          meta: { viewTransitionScope: 'section' satisfies ViewTransitionScope },
        }
      ]
    }
  ]
});

type ViewTransition = {
  finished: Promise<void>;
};

type ViewTransitionStarter = (
  updateCallback: () => void | Promise<void>,
) => ViewTransition;

const documentWithTransition = typeof document === 'undefined'
  ? null
  : (document as Document & { startViewTransition?: ViewTransitionStarter });

const prefersReducedMotion = typeof window === 'undefined'
  ? null
  : window.matchMedia('(prefers-reduced-motion: reduce)');

let activeTransition: Promise<void> | null = null;

function getPreferredViewTransitionScope(route: { meta: Record<string, unknown> }): ViewTransitionScope {
  return route.meta.viewTransitionScope === 'section' ? 'section' : 'page';
}

function setViewTransitionScope(scope: ViewTransitionScope) {
  if (typeof document === 'undefined') {
    return;
  }

  document.documentElement.dataset.viewTransitionScope = scope;
}

function attachViewTransition(
  navigation: Promise<unknown>,
  transitionScope: ViewTransitionScope,
  targetScope: ViewTransitionScope,
) {
  const startViewTransition = documentWithTransition?.startViewTransition?.bind(documentWithTransition);
  if (!startViewTransition || prefersReducedMotion?.matches || activeTransition) {
    setViewTransitionScope(targetScope);
    return;
  }

  setViewTransitionScope(transitionScope);
  const transition = startViewTransition(() => navigation.catch(() => undefined));
  activeTransition = transition.finished
    .catch(() => undefined)
    .finally(() => {
      setViewTransitionScope(targetScope);
      activeTransition = null;
    });
}

function wrapNavigationMethod(
  method: (to: RouteLocationRaw) => Promise<unknown>,
) {
  return (to: RouteLocationRaw) => {
    const target = router.resolve(to);
    const current = router.currentRoute.value;
    const currentFullPath = router.currentRoute.value.fullPath;
    const navigation = method(to);

    if (target.fullPath !== currentFullPath) {
      const currentScope = getPreferredViewTransitionScope(current);
      const targetScope = getPreferredViewTransitionScope(target);
      const transitionScope =
        currentScope === 'section' && targetScope === 'section'
          ? 'section'
          : 'page';

      attachViewTransition(navigation, transitionScope, targetScope);
    }

    return navigation;
  };
}

const rawPush = router.push.bind(router);
const rawReplace = router.replace.bind(router);

router.push = wrapNavigationMethod(rawPush) as typeof router.push;
router.replace = wrapNavigationMethod(rawReplace) as typeof router.replace;

export default router;
