// Library view: every indexed note in a sortable, filterable table.
import { api } from './api.js';
import { $$, el, fmtDate, fmtNum, iconEl, timeAgo, typeBadge } from './utils.js';
import { go, paramsObject } from './router.js';

let root, route, notes = [], sortKey = 'title', sortDir = 1, filter = '', active = null;
let ui = {};

const COLUMNS = [
  ['title', 'Title', ''], ['type', 'Type', ''], ['words', 'Words', 'num'],
  ['modified', 'Edited', 'num'], ['path', 'Path', ''],
];

function visibleNotes() {
  const f = filter.trim().toLowerCase();
  const rows = notes.filter(n => !f || `${n.title} ${n.path} ${n.type}`.toLowerCase().includes(f));
  const numeric = sortKey === 'words' || sortKey === 'modified';
  return rows.sort((a, b) => sortDir * (numeric ? a[sortKey] - b[sortKey] : String(a[sortKey]).localeCompare(String(b[sortKey]))));
}

function renderHead() {
  ui.thead.replaceChildren(el('tr', {}, COLUMNS.map(([key, label, cls]) =>
    el('th', { class: cls, scope: 'col', 'aria-sort': key === sortKey ? (sortDir === 1 ? 'ascending' : 'descending') : 'none' },
      el('button', { type: 'button', onclick: () => {
        sortDir = key === sortKey ? -sortDir : 1; sortKey = key; renderHead(); renderRows();
      } }, label, key === sortKey ? iconEl(sortDir === 1 ? 'up' : 'down', 13) : iconEl('sort', 13))))));
}

function renderRows() {
  const rows = visibleNotes();
  ui.count.textContent = `${rows.length} of ${notes.length} notes`;
  ui.tbody.replaceChildren(...rows.map(n => {
    const open = () => go('library', { ...paramsObject(route), note: n.path });
    return el('tr', { tabindex: '0', 'data-path': n.path, 'data-nav': '', class: n.path === active ? 'active' : '',
      onclick: open, onkeydown: e => { if (e.key === 'Enter') open(); } },
      el('td', { class: 'title' }, n.title), el('td', {}, typeBadge(n.type)),
      el('td', { class: 'num' }, fmtNum(n.words)),
      el('td', { class: 'num', title: fmtDate(n.modified) }, timeAgo(n.modified)),
      el('td', { class: 'path' }, n.path));
  }));
  if (!rows.length) ui.tbody.append(el('tr', {}, el('td', { colspan: COLUMNS.length, style: 'text-align:center;color:var(--muted);padding:32px;cursor:default' }, 'No notes match your filter.')));
}

export const libraryView = {
  name: 'library',

  mount(r) {
    root = r; filter = '';
    ui.count = el('span', { class: 'status', style: 'margin:0' });
    ui.filter = el('input', { class: 'filter', type: 'search', placeholder: 'Filter notes…', 'aria-label': 'Filter notes',
      oninput: e => { filter = e.target.value; renderRows(); } });
    ui.thead = el('thead'); ui.tbody = el('tbody');
    root.replaceChildren(el('section', { class: 'page' },
      el('div', { class: 'page-head' }, el('h1', {}, 'All notes'), el('p', {}, 'Every note in the index. Click a row to read it.')),
      el('div', { class: 'toolbar' }, ui.filter, el('span', { class: 'grow' }), ui.count),
      el('div', { class: 'card table-wrap' }, el('table', {}, ui.thead, ui.tbody))));
    renderHead();
  },

  async update(r) {
    route = r; active = r.params.get('note');
    try { notes = (await api.notes()).notes; }
    catch { ui.count.textContent = 'Could not load notes.'; return; }
    renderRows();
  },

  activate(path) { active = path; $$('tbody tr', root).forEach(tr => tr.classList.toggle('active', tr.dataset.path === path)); },
};
