import '@testing-library/jest-dom/vitest';

if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

if (typeof window !== 'undefined' && !window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

if (typeof window !== 'undefined' && !window.visualViewport) {
  Object.defineProperty(window, 'visualViewport', {
    configurable: true,
    value: {
      height: window.innerHeight,
      offsetTop: 0,
      addEventListener: () => {},
      removeEventListener: () => {},
    },
  });
}
