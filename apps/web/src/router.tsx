import {
  createRouter,
  createRootRoute,
  createRoute,
  lazyRouteComponent,
  Outlet,
  redirect,
  type RouterHistory,
} from '@tanstack/react-router';
import { getDevAuth } from '@/services/dev-auth';

const rootRoute = createRootRoute({
  component: function RootLayout() {
    return <Outlet />;
  },
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    if (getDevAuth()) {
      throw redirect({ to: '/demo' });
    }
  },
  component: lazyRouteComponent(
    () => import('@/features/auth/components/LoginScreen'),
    'LoginScreen',
  ),
});

const demoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/demo',
  beforeLoad: () => {
    if (!getDevAuth()) {
      throw redirect({ to: '/' });
    }
  },
  component: lazyRouteComponent(
    () => import('@/features/avatar/components/LiveSessionScreen'),
    'LiveSessionRoute',
  ),
});

const routeTree = rootRoute.addChildren([loginRoute, demoRoute]);

type CreateAppRouterOptions = {
  history?: RouterHistory;
};

export function createAppRouter(options: CreateAppRouterOptions = {}) {
  return createRouter({
    routeTree,
    defaultPreload: 'intent',
    defaultPendingMs: 0,
    defaultPendingMinMs: 0,
    ...options,
  });
}

export const router = createAppRouter();

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
