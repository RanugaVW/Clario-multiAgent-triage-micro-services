import '@testing-library/jest-dom';
import { vi, beforeAll, afterAll } from 'vitest';

// jsdom has no IntersectionObserver and framer-motion's whileInView needs one. Nothing ever intersects in tests.
if (!('IntersectionObserver' in globalThis)) {
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return [];
      }
    }
  );
}

// Global mock for fetch if needed
global.fetch = vi.fn();

// Mock crypto.randomUUID
Object.defineProperty(global.crypto, 'randomUUID', {
  value: () => `test-uuid-${Math.random().toString(36).substr(2, 9)}`,
});

// Suppress console errors in tests (optional)
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});
