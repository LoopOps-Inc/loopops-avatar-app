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
  component: lazyRouteComponent(
    () => import('@/features/avatar/components/LiveSessionScreen'),
    'LiveSessionRoute',
  ),
});

const demoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/demo',
  beforeLoad: () => {
    throw redirect({ to: '/' });
  },
});

const routeTree = rootRoute.addChildren([indexRoute, demoRoute]);

export const router = createRouter({ routeTree, defaultPreload: 'intent' });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
