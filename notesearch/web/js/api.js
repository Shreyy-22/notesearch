// Thin wrapper around the JSON API.

async function request(url, options) {
  const res = await fetch(url, options);
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON error page */ }
  if (!res.ok) throw new Error((data && data.error) || res.statusText || 'Request failed');
  return data;
}

const qs = obj => new URLSearchParams(
  Object.entries(obj).filter(([, v]) => v !== undefined && v !== null && v !== '')
).toString();

export const api = {
  search: params => request('/api/search?' + qs(params)),
  suggest: q => request('/api/suggest?' + qs({ q })),
  doc: params => request('/api/doc?' + qs(params)),
  notes: () => request('/api/notes'),
  overview: () => request('/api/overview'),
  stats: () => request('/api/stats'),
  reindex: () => request('/api/reindex', { method: 'POST' }),
};
