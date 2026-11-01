// Overview: a dashboard of what is in the notes folder.
import { api } from './api.js';
import { el, fmtNum, iconEl, timeAgo, typeBadge, TYPE_LABELS } from './utils.js';
import { go } from './router.js';

let root;

/** swap the 2nd and 3rd letters: "graph" -> "grpah" (a typo the search will fix) */
const typo = w => (w.length >= 4 ? w[0] + w[2] + w[1] + w.slice(3) : w);

function statCard(icon, label, value, sub) {
  return el('div', { class: 'card stat' },
    el('div', { class: 'k' }, iconEl(icon, 16), label),
    el('div', { class: 'v' }, value),
    el('div', { class: 's' }, sub));
}

function typesCard(types, total) {
  const entries = Object.entries(types).sort((a, b) => b[1] - a[1]);
  const bar = el('div', { class: 'bar', role: 'img', 'aria-label': 'File type breakdown' },
    entries.map(([t, n]) => el('span', { class: `type-${TYPE_LABELS[t] ? t : 'other'}`, style: `width:${(n / total) * 100}%`, title: `${t}: ${n}` })));
  const legend = el('div', { class: 'legend' },
    entries.map(([t, n]) => el('div', { class: `type-${TYPE_LABELS[t] ? t : 'other'}` },
      el('i'), TYPE_LABELS[t] || t.toUpperCase(), el('b', {}, `${n} ${n === 1 ? 'note' : 'notes'}`))));
  return el('div', { class: 'card card-pad' }, el('h2', {}, 'File types'), bar, legend);
}

function wordsCard(words) {
  return el('div', { class: 'card card-pad' }, el('h2', {}, 'Most used words'),
    el('div', { class: 'cloud' }, words.map(w =>
      el('button', { class: 'chip', type: 'button', title: `Search “${w.word}”`, onclick: () => go('search', { q: w.word }) },
        w.word, el('span', { class: 'n' }, w.count)))));
}

function recentCard(items) {
  return el('div', { class: 'card card-pad' }, el('h2', {}, 'Recently edited'),
    el('div', { class: 'list' }, items.map(n =>
      el('button', { type: 'button', onclick: () => go('overview', { note: n.path }) },
        typeBadge(n.type), el('span', { class: 't' }, n.title), el('span', { class: 'm' }, timeAgo(n.modified))))));
}

function tipsCard(words) {
  const [a, b, c] = words.map(w => w.word);
  const rows = [];
  if (a) rows.push([a, 'A single word']);
  if (a && b) rows.push([`${a} -${b}`, 'Leave out notes with a word']);
  if (c) rows.push([typo(c), 'Typos are fixed for you']);
  return el('div', { class: 'card card-pad' }, el('h2', {}, 'Try it'),
    el('div', { class: 'tips' }, rows.map(([q, d]) =>
      el('button', { type: 'button', onclick: () => go('search', { q }) }, el('code', {}, q), el('span', {}, d)))),
    el('p', { style: 'color:var(--faint);font-size:.82rem;margin-top:12px' },
      'Put words in “quotes” for an exact phrase. Press Tab to accept an autocomplete suggestion.'));
}

export const overviewView = {
  name: 'overview',
  mount(r) {
    root = r;
    root.replaceChildren(el('section', { class: 'page' },
      el('div', { class: 'page-head' }, el('h1', {}, 'Overview'), el('p', {}, 'Loading…')),
      el('div', { class: 'stats' }, [0, 1, 2, 3].map(() => el('div', { class: 'card stat' },
        el('div', { class: 'skeleton', style: 'height:14px;width:50%' }),
        el('div', { class: 'skeleton', style: 'height:30px;width:70%;margin-top:10px' }))))));
  },
  async update() {
    let d;
    try { d = await api.overview(); }
    catch { root.replaceChildren(el('div', { class: 'empty' }, el('h2', {}, 'Could not reach the server'))); return; }

    if (!d.notes) {
      root.replaceChildren(el('div', { class: 'empty' },
        el('div', { class: 'ico' }, iconEl('folder', 24)),
        el('h2', {}, 'No notes found yet'),
        el('p', {}, `Add .txt, .md or .pdf files to “${d.folder}”, then press Rescan folder.`)));
      return;
    }
    root.replaceChildren(el('section', { class: 'page' },
      el('div', { class: 'page-head' }, el('h1', {}, 'Overview'),
        el('p', {}, `Everything in “${d.folder}”, indexed and ready to search.`)),
      el('div', { class: 'stats' },
        statCard('file', 'Notes', fmtNum(d.notes), Object.keys(d.types).length + ' file types'),
        statCard('layers', 'Unique words', fmtNum(d.unique_words), 'in the index'),
        statCard('words', 'Total words', fmtNum(d.total_words), `${fmtNum(Math.round(d.total_words / d.notes))} per note`),
        statCard('database', 'Index size', d.index_kb + ' KB', 'saved on disk')),
      el('div', { class: 'grid-2' }, typesCard(d.types, d.notes), wordsCard(d.top_words)),
      el('div', { class: 'grid-2' }, recentCard(d.recent), tipsCard(d.top_words))));
  },
  activate() {},
};
