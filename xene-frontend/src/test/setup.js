// Global test setup — runs before every test file via vite.config.js setupFiles.

import '@testing-library/jest-dom'

// jsdom does not implement IntersectionObserver.
// This stub lets components that use it (ArtistCard) mount without crashing.
// observe() fires the callback immediately with isIntersecting=true so tests
// can assert on the "visible" branch of conditional renders.
class MockIntersectionObserver {
  constructor(callback) {
    this.callback = callback
  }
  observe(el) {
    this.callback([{ isIntersecting: true, target: el }])
  }
  unobserve() {}
  disconnect() {}
}

global.IntersectionObserver = MockIntersectionObserver
