// NoteSearch frontend: wires the router, views, reader, global search box and shortcuts.
import { api } from './api.js';
import { $, $$, debounce, el, hydrateIcons, icon, iconEl, setTheme, currentTheme, toast } from './utils.js';
import { go, onRoute, parseHash, paramsObject, refresh, start } from './router.js';
import { closeReader, initReader, isOpen, openReader, step } from './reader.js';
import { overviewView } from './overview.js';
import { searchView, searchOpts, remember } from './search.js';
import { libraryView } from './library.js';

const VIEWS = { overview: overviewView, search: searchView, library: libraryView };
const TITLES = { overview: 'Overview', search: 'Search', library: 'All notes' };
let current = null, lastKey = null;

/* ======================= routing ======================= */
const routeKey = r => r.view + '?' + [...r.params].filter(([k]) => k !== 'note').sort().map(([k, v]) => k + '=' + v).join('&');

function handle(route) {
  const view = VIEWS[route.view];
  $$('[data-view]').forEach(a => a.toggleAttribute('aria-current', a.dataset.view === route.view));
  $$('[data-view][aria-current]').forEach(a => a.setAttribute('aria-current', 'page'));

  if (current !== view) {                     // switching views: rebuild the page
    current?.unmount?.();
    view.mount($('#view'));
    current = view; lastKey = null;
    window.scrollTo({ top: 0 });
  }
  const key = routeKey(route);
  if (key !== lastKey) { lastKey = key; view.update(route); }

  const q = route.params.get('q') || '';
  const input = $('#q');
  if (route.view === 'search' && document.activeElement !== input && input.value.trim() !== q.trim()) { input.value = q; paintBox(); }

  const note = route.params.get('note');
  if (note) { openReader(note, route.view === 'search' ? q.trim() : '', searchOpts(route.params)); view.activate?.(note); }
  else { closeReader(); view.activate?.(null); }
  document.title = (route.view === 'search' && q.trim() ? q.trim() + ' · ' : '') + TITLES[route.view] + ' · NoteSearch';
}

function closeNote() {
  const r = parseHash(), p = paramsObject(r);
  delete p.note;
  go(r.view, p);
}

/* ======================= global search box ======================= */
const input = $('#q'), box = $('#searchBox'), sugg = $('#suggest');
let items = [], sel = -1;

const paintBox = () => box.classList.toggle('has-text', !!input.value);

const commit = debounce(() => {
  const r = parseHash(), text = input.value;
  if (r.view !== 'search' && !text.trim()) return;
  go('search', { ...(r.view === 'search' ? paramsObject(r) : {}), q: text.trim() ? text : '' }, { replace: r.view === 'search' });
}, 160);

function hideSugg() { sugg.hidden = true; items = []; sel = -1; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); }

function showSugg(list, typed) {
  items = list; sel = -1;
  sugg.replaceChildren(...list.map((w, i) => el('div', {
    role: 'option', id: 'sg' + i, 'aria-selected': 'false',
    onmousedown: e => { e.preventDefault(); accept(w); },
  }, iconEl('search', 14), el('span', {}, w.startsWith(typed) ? [typed, el('b', {}, w.slice(typed.length))] : w))));
  sugg.hidden = !list.length;
  input.setAttribute('aria-expanded', String(!!list.length));
}

function select(delta) {
  if (!items.length) return;
  sel = (sel + delta + items.length) % items.length;
  [...sugg.children].forEach((c, i) => c.setAttribute('aria-selected', String(i === sel)));
  input.setAttribute('aria-activedescendant', 'sg' + sel);
}

function accept(word) { input.value = word + ' '; paintBox(); hideSugg(); input.focus(); commit.cancel(); commit(); }

const fetchSuggestions = debounce(async () => {
  const typed = input.value;
  if (!typed.trim() || /\s$/.test(typed)) return hideSugg();
  try { const { suggestions } = await api.suggest(typed); if (input.value === typed) showSugg(suggestions, typed); } catch { /* ignore */ }
}, 120);

input.addEventListener('input', () => { paintBox(); commit(); fetchSuggestions(); });
input.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') { e.preventDefault(); select(1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); select(-1); }
  else if (e.key === 'Tab' && items.length) { e.preventDefault(); accept(items[sel >= 0 ? sel : 0]); }
  else if (e.key === 'Enter') {
    if (sel >= 0) { e.preventDefault(); accept(items[sel]); return; }
    hideSugg(); commit.cancel(); remember(input.value);
    const r = parseHash(); go('search', { ...(r.view === 'search' ? paramsObject(r) : {}), q: input.value.trim() }, { replace: r.view === 'search' });
  }
  else if (e.key === 'Escape') hideSugg();
});
input.addEventListener('blur', () => setTimeout(hideSugg, 120));
$('#btnClear').addEventListener('click', () => { input.value = ''; paintBox(); hideSugg(); input.focus(); commit.cancel(); const r = parseHash(); if (r.view === 'search') go('search', { ...paramsObject(r), q: '' }, { replace: true }); });

/* ======================= sidebar actions ======================= */
async function loadStats() {
  try {
    const s = await api.stats();
    $('#navCount').textContent = s.notes;
    $('#folderName').textContent = s.folder;
  } catch { $('#folderName').textContent = 'offline'; }
}

$('#btnReindex').addEventListener('click', async e => {
  const btn = e.currentTarget, label = $('.label', btn);
  btn.disabled = true; btn.classList.add('spin'); label.textContent = 'Scanning…';
  try {
    const s = await api.reindex();
    toast(s.added + s.updated + s.removed
      ? `+${s.added} added, ~${s.updated} updated, −${s.removed} removed`
      : 'Already up to date');
    s.errors.forEach(m => toast(m, 'error'));
    await loadStats();
    lastKey = null; refresh();
  } catch (err) { toast('Rescan failed: ' + err.message, 'error'); }
  finally { btn.disabled = false; btn.classList.remove('spin'); label.textContent = 'Rescan folder'; }
});

function paintTheme() {
  const dark = currentTheme() === 'dark';
  for (const b of [$('#btnTheme'), $('#btnThemeTop')]) b.innerHTML = icon(dark ? 'sun' : 'moon', 18);
}
function toggleTheme() { setTheme(currentTheme() === 'dark' ? 'light' : 'dark'); paintTheme(); }
$('#btnTheme').addEventListener('click', toggleTheme);
$('#btnThemeTop').addEventListener('click', toggleTheme);

const keys = $('#keysDialog');
$('#btnKeys').addEventListener('click', () => keys.showModal());
$('#keysClose').addEventListener('click', () => keys.close());
keys.addEventListener('click', e => { if (e.target === keys) keys.close(); });

/* ======================= keyboard shortcuts ======================= */
const typing = t => t && (['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName) || t.isContentEditable);

document.addEventListener('keydown', e => {
  if (e.metaKey || e.ctrlKey || e.altKey || keys.open) return;
  const inField = typing(e.target);

  if (e.key === 'Escape') { if (!inField && isOpen()) closeNote(); return; }
  if (inField) return;

  switch (e.key) {
    case '/': e.preventDefault(); input.focus(); input.select(); break;
    case '?': keys.showModal(); break;
    case 't': toggleTheme(); break;
    case 'n': step(1); break;
    case 'N': step(-1); break;
    case 'j': case 'k': {
      const rows = $$('[data-nav]');
      if (!rows.length) break;
      const at = rows.indexOf(document.activeElement);
      const next = e.key === 'j' ? Math.min(at + 1, rows.length - 1) : Math.max(at - 1, 0);
      rows[at === -1 ? 0 : next].focus();
      break;
    }
  }
});

/* ======================= boot ======================= */
hydrateIcons();
$('#logoSide').innerHTML = icon('logo', 18);
$('#logoTop').innerHTML = icon('logo', 18);
paintTheme();
initReader(closeNote);
onRoute(handle);
loadStats();
start();
