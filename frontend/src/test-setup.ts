// jsdom lacks ResizeObserver, which Vuetify's auto-growing textarea uses.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
