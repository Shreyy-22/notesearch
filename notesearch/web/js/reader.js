// The note reader: docked panel (wide screens) / drawer (narrow screens).
import { api } from './api.js';
import { $, el, fmtDate, fmtNum, timeAgo, toast, typeBadge } from './utils.js';

let state = { key: null, path: null, marks: [], cur: -1 };
let onClose = () => {};

export function initReader(closeCallback) {
  onClose = closeCallback;
  $('#rClose').addEventListener('click', () => onClose());
  $('#scrim').addEventListener('click', () => onClose());
  $('#rNext').addEventListener('click', () => step(1));
  $('#rPrev').addEventListener('click', () => step(-1));
  $('#rCopy').addEventListener('click', copyPath);
}

export const isOpen = () => !$('#reader').hidden;

export async function openReader(path, query, opts) {
  const key = [path, query, opts.fuzzy, opts.any].join('|');
  const reader = $('#reader');
  if (state.key === key && !reader.hidden) return;        // already showing exactly this
  state = { key, path, marks: [], cur: -1 };
  reader.hidden = false;
  document.body.classList.add('reader-open');
  $('#scrim').hidden = innerWidth >= 1280;                 // docked on wide screens: no backdrop
  $('#rTitle').textContent = path;
  $('#rMeta').replaceChildren();
  $('#rCount').textContent = '';
  $('#rBody').replaceChildren(...[90, 100, 70, 95, 60].map(w => el('span', { class: 'sk skeleton', style: `width:${w}%` })));
  try {
    const d = await api.doc({ path, q: query, fuzzy: opts.fuzzy, any: opts.any, prefix: 1 });
    if (state.key !== key) return;                          // user opened another note meanwhile
    $('#rTitle').textContent = d.title;
    $('#rMeta').replaceChildren(
      typeBadge(d.type), el('span', {}, `${fmtNum(d.words)} words`),
      el('span', { title: fmtDate(d.modified) }, `Edited ${timeAgo(d.modified)}`),
      el('span', { style: 'font-family:var(--mono)' }, d.path));
    $('#rBody').innerHTML = d.html;                         // escaped on the server; only <mark> added
    $('#rBody').scrollTop = 0;
    state.marks = [...$('#rBody').querySelectorAll('mark')];
    for (const id of ['rPrev', 'rNext']) $('#' + id).style.display = state.marks.length ? '' : 'none';
    if (state.marks.length) step(1);
    else $('#rCount').textContent = query ? 'No highlighted words' : '';
  } catch (err) {
    toast('Could not open note: ' + err.message, 'error');
    onClose();
  }
}

export function closeReader() {
  state = { key: null, path: null, marks: [], cur: -1 };
  $('#reader').hidden = true;
  $('#scrim').hidden = true;
  document.body.classList.remove('reader-open');
}

export function step(delta) {
  const { marks } = state;
  if (!marks.length) return;
  if (state.cur >= 0) marks[state.cur].classList.remove('cur');
  state.cur = (state.cur + delta + marks.length) % marks.length;
  const m = marks[state.cur];
  m.classList.add('cur');
  m.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  $('#rCount').textContent = `${state.cur + 1} of ${marks.length} matches`;
}

async function copyPath() {
  try { await navigator.clipboard.writeText(state.path); toast('Path copied'); }
  catch { toast(state.path); }                              // clipboard blocked: just show it
}
