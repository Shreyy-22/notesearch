// Search view: filters, results, empty states.
import { api } from './api.js';
import { $, $$, el, fmtNum, iconEl, store, timeAgo, typeBadge, TYPE_LABELS } from './utils.js';
import { go, paramsObject } from './router.js';

let root, route, seq = 0, ui = {};
let outsideClick = null;

export function searchOpts(params) {
  return {
    fuzzy: params.get('fuzzy') === '0' ? 0 : 1,
    any: params.get('any') === '1' ? 1 : 0,
    prefix: 1,
    k: +params.get('k') || 10,
    types: params.get('types') || '',
    sort: params.get('sort') || 'relevance',
  };
}

/* ---------- recent searches ---------- */
export function remember(q) {
  q = (q || '').trim();
  if (q.length < 2) return;
  store.set('ns-recent', [q, ...store.get('ns-recent', []).filter(x => x !== q)].slice(0, 6));
}

/* ---------- state changes go through the URL ---------- */
const setParams = changes => go('search', { ...paramsObject(route), ...changes }, { replace: true });
const openNote = (path, q) => { remember(q); go('search', { ...paramsObject(route), note: path }); };

/* ---------- building blocks ---------- */
function toolbar() {
  ui.chips = Object.entries(TYPE_LABELS).map(([t, label]) =>
    el('button', { class: 'chip', type: 'button', 'aria-pressed': 'false', 'data-type': t, onclick: () => {
      const set = new Set((route.params.get('types') || '').split(',').filter(Boolean));
      set.has(t) ? set.delete(t) : set.add(t);
      setParams({ types: [...set].join(',') });
    } }, label));

  ui.sort = el('select', { 'aria-label': 'Sort results', onchange: e => setParams({ sort: e.target.value === 'relevance' ? '' : e.target.value }) },
    el('option', { value: 'relevance' }, 'Best match'), el('option', { value: 'newest' }, 'Newest first'));

  ui.fuzzy = el('input', { type: 'checkbox', onchange: e => setParams({ fuzzy: e.target.checked ? '' : '0' }) });
  ui.any = el('input', { type: 'checkbox', onchange: e => setParams({ any: e.target.checked ? '1' : '' }) });
  ui.k = el('select', { 'aria-label': 'Results to show', onchange: e => setParams({ k: e.target.value === '10' ? '' : e.target.value }) },
    [5, 10, 20, 50].map(n => el('option', { value: n }, n)));
  ui.menu = el('details', { class: 'menu' },
    el('summary', { class: 'btn' }, iconEl('sliders', 16), 'Options'),
    el('div', { class: 'menu-panel' },
      el('label', {}, ui.fuzzy, el('span', {}, 'Fix typos', el('small', {}, 'Find words even when misspelled'))),
      el('label', {}, ui.any, el('span', {}, 'Match any word', el('small', {}, 'Instead of requiring every word'))),
      el('div', { class: 'sel' }, el('span', {}, 'Results to show'), ui.k)));

  return el('div', { class: 'toolbar' }, ui.chips, el('span', { class: 'grow' }), ui.sort, ui.menu);
}

function syncControls(o) {
  const types = new Set(o.types.split(',').filter(Boolean));
  ui.chips.forEach(c => c.setAttribute('aria-pressed', types.has(c.dataset.type)));
  ui.sort.value = o.sort;
  ui.fuzzy.checked = !!o.fuzzy;
  ui.any.checked = !!o.any;
  ui.k.value = String(o.k);
}

function skeletons() {
  return [0, 1, 2].map(() => el('div', { class: 'card result' },
    el('div', { class: 'skeleton', style: 'height:16px;width:45%' }),
    el('div', { class: 'skeleton', style: 'height:12px;width:30%;margin-top:10px' }),
    el('div', { class: 'skeleton', style: 'height:12px;width:90%;margin-top:14px' }),
    el('div', { class: 'skeleton', style: 'height:12px;width:75%;margin-top:8px' })));
}

function resultCard(h, q, active) {
  const open = () => openNote(h.path, q);
  return el('article', {
    class: 'card result' + (h.path === active ? ' active' : ''), tabindex: '0', role: 'button',
    'data-path': h.path, 'data-nav': '', 'aria-label': `Open ${h.title}`,
    onclick: open, onkeydown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } },
  },
    el('div', { class: 'result-top' }, typeBadge(h.type), el('h3', {}, h.title),
      el('span', { class: 'score', title: 'Relevance score' }, h.score.toFixed(2))),
    el('div', { class: 'meta' },
      el('span', {}, iconEl('folder', 13), el('span', { class: 'path' }, h.path)),
      el('span', {}, iconEl('clock', 13), timeAgo(h.modified)),
      el('span', {}, `${fmtNum(h.words)} words`)),
    el('p', { class: 'snippet', html: h.snippet }),                 // escaped on the server; only <mark> added
    el('div', { class: 'meter' }, el('i', { style: `width:${Math.max(6, h.relative * 100)}%` })));
}

function intro() {
  const recent = store.get('ns-recent', []);
  const kids = [
    el('div', { class: 'ico' }, iconEl('search', 24)),
    el('h2', {}, 'Search your notes'),
    el('p', {}, 'Start typing above. Misspelled words are fixed, and results are ranked by relevance.'),
    el('div', { class: 'actions' },
      el('button', { class: 'btn', type: 'button', onclick: () => go('library') }, iconEl('library', 16), 'Browse all notes'),
      el('button', { class: 'btn', type: 'button', onclick: () => go('overview') }, iconEl('home', 16), 'Overview')),
  ];
  if (recent.length) {
    kids.push(el('div', { class: 'sub' }, 'Recent searches'),
      el('div', { class: 'actions' },
        recent.map(t => el('button', { class: 'chip', type: 'button', onclick: () => go('search', { q: t }) }, t)),
        el('button', { class: 'chip', type: 'button', 'aria-label': 'Clear recent searches',
          onclick: () => { store.set('ns-recent', []); ui.results.replaceChildren(intro()); } }, 'Clear')));
  }
  return el('div', { class: 'empty' }, kids);
}

function noResults(q, o) {
  const actions = [];
  if (!o.any) actions.push(el('button', { class: 'btn', type: 'button', onclick: () => setParams({ any: '1' }) }, 'Match any word'));
  if (o.types) actions.push(el('button', { class: 'btn', type: 'button', onclick: () => setParams({ types: '' }) }, 'Clear file filters'));
  if (!o.fuzzy) actions.push(el('button', { class: 'btn', type: 'button', onclick: () => setParams({ fuzzy: '' }) }, 'Fix typos'));
  return el('div', { class: 'empty' },
    el('div', { class: 'ico' }, iconEl('search', 24)),
    el('h2', {}, 'No notes found'),
    el('p', {}, `Nothing matches “${q}”. Try fewer words or check the spelling.`),
    actions.length ? el('div', { class: 'actions' }, actions) : null);
}

/* ---------- view contract ---------- */
export const searchView = {
  name: 'search',

  mount(r) {
    root = r;
    ui.status = el('div', { class: 'status', role: 'status', 'aria-live': 'polite' });
    ui.results = el('div', { id: 'results' });
    root.replaceChildren(el('section', { class: 'page' },
      el('div', { class: 'page-head' }, el('h1', {}, 'Search')),
      toolbar(), ui.status, ui.results));
    outsideClick = e => { if (ui.menu.open && !ui.menu.contains(e.target)) ui.menu.open = false; };
    document.addEventListener('click', outsideClick);
  },

  unmount() { document.removeEventListener('click', outsideClick); seq++; },

  async update(r) {
    route = r;
    const o = searchOpts(r.params);
    const q = (r.params.get('q') || '').trim();
    syncControls(o);
    if (!q) { seq++; ui.status.textContent = ''; ui.results.classList.remove('loading'); ui.results.replaceChildren(intro()); return; }

    const my = ++seq;
    ui.results.classList.add('loading');
    if (!ui.results.querySelector('.result')) ui.results.replaceChildren(...skeletons());
    let data;
    try { data = await api.search({ q, k: o.k, fuzzy: o.fuzzy, any: o.any, prefix: 1, types: o.types, sort: o.sort }); }
    catch { if (my === seq) { ui.status.textContent = 'Could not reach the server.'; ui.results.classList.remove('loading'); } return; }
    if (my !== seq) return;                                          // a newer search already started

    ui.results.classList.remove('loading');
    if (!data.results.length) { ui.status.textContent = '0 results'; ui.results.replaceChildren(noResults(q, o)); return; }
    const n = data.results.length, active = r.params.get('note');
    ui.status.textContent = `${n} ${n === 1 ? 'result' : 'results'} for “${q}” · ${data.took_ms} ms`;
    ui.results.replaceChildren(...data.results.map(h => resultCard(h, q, active)));
  },

  activate(path) { $$('.result', root).forEach(c => c.classList.toggle('active', c.dataset.path === path)); },
};
