// Hash router: #/<view>?key=value.  The URL is the single source of truth, so every
// search, filter and open note can be bookmarked, shared and used with the Back button.

const VIEWS = ['overview', 'search', 'library'];
const listeners = new Set();
let last = null;

const currentHash = () => location.hash || '#/';

export function parseHash() {
  const [path, query = ''] = currentHash().replace(/^#/, '').split('?');
  const name = path.replace(/^\//, '').split('/')[0];
  return { view: VIEWS.includes(name) ? name : 'overview', params: new URLSearchParams(query) };
}

export function buildHash(view, params = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') p.set(k, v);
  const s = p.toString();
  return '#/' + (view === 'overview' ? '' : view) + (s ? '?' + s : '');
}

/** key/value object of the current params (handy for spreading). */
export const paramsObject = route => Object.fromEntries(route.params);

function emit() {
  last = currentHash();
  const route = parseHash();
  listeners.forEach(fn => fn(route));
}

export function onRoute(fn) { listeners.add(fn); }

export function go(view, params = {}, { replace = false } = {}) {
  const hash = buildHash(view, params);
  if (hash === currentHash()) return;
  history[replace ? 'replaceState' : 'pushState'](null, '', hash);
  emit();
}

/** re-run the current route (e.g. after a rescan) */
export const refresh = () => emit();

function onNavigate() { if (currentHash() !== last) emit(); }
window.addEventListener('hashchange', onNavigate);
window.addEventListener('popstate', onNavigate);
export const start = () => emit();
