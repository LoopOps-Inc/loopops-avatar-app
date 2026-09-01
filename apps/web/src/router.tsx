import {
  createRouter,
  createRootRoute,
  createRoute,
  lazyRouteComponent,
  redirect,
  Outlet,
} from '@tanstack/react-router';

const rootRoute = createRootRoute({
  component: function RootLayout() {
    return <Outlet />;
  },
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/advisor' });
  },
});

const advisorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/advisor',
  component: lazyRouteComponent(
    () => import('@/features/advisor/components/AdvisorPage'),
    'AdvisorRoute',
  ),
});

const demoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/demo',
  component: lazyRouteComponent(
    () => import('@/features/avatar/components/AvatarDemoPage'),
    'AvatarDemoRoute',
  ),
});

const routeTree = rootRoute.addChildren([indexRoute, advisorRoute, demoRoute]);

export const router = createRouter({ routeTree, defaultPreload: 'intent' });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
