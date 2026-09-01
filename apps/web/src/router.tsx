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
    throw redirect({ to: '/demo' });
  },
});

const demoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/demo',
  component: lazyRouteComponent(
    () => import('@/features/avatar/components/LiveSessionScreen'),
    'LiveSessionRoute',
  ),
});

const routeTree = rootRoute.addChildren([indexRoute, demoRoute]);

export const router = createRouter({ routeTree, defaultPreload: 'intent' });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
