'use strict';
/* RuneVest shared Update Watch renderer.
   Reads window.RV_ROADMAPS (data/roadmaps.js, hand-curated from official sources).
   Shows exact days only where the data has `date`, months only where it has `month`. */
(function () {
  const R = window.RV_ROADMAPS || { games: {} };
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const BASIS = {
    official: ['Official', 'Timing stated in an official Jagex post or press release'],
    released: ['Released', 'Already in the game, kept for context'],
    poll: ['In poll', 'Proposed; depends on an open player poll'],
    'roadmap-image': ['Roadmap graphic', 'Read off Jagex\'s roadmap graphic, as transcribed by the game\'s official wiki'],
    're-evaluation': ['Under review', 'Announced, then put under review by Jagex'],
  };
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function today() { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
  function parseDay(s) { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); }
  // sort key: exact day, else month (end of month), else year in text, else last
  function sortKey(it) {
    if (it.date) return parseDay(it.date).getTime();
    if (it.month) { const [y, m] = it.month.split('-').map(Number); return new Date(y, m, 0).getTime() + 1; }
    const y = /(\d{4})/.exec(it.when || ''); if (y) { const yr = +y[1]; const half = /first half|early/i.test(it.when) ? 5 : /summer/i.test(it.when) ? 7 : /autumn|third/i.test(it.when) ? 10 : 12; return new Date(yr, half, 0).getTime() + 2; }
    return Infinity;
  }
  function whenLabel(it) {
    if (it.date) { const d = parseDay(it.date); return `${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`; }
    if (it.month) { const [y, m] = it.month.split('-').map(Number); return (it.when && /mid/i.test(it.when) ? 'Mid ' : '') + MONTHS[m - 1] + ' ' + y; }
    return it.when || 'No date announced';
  }
  function relLabel(it) {
    const t = today();
    if (it.date) {
      const days = Math.round((parseDay(it.date) - t) / 864e5);
      if (days === 0) return { txt: it.basis === 'released' ? 'Out today' : 'Today', soon: true, past: false };
      if (days < 0) return { txt: it.basis === 'released' ? 'Out ' + (-days) + 'd ago' : (-days) + 'd ago', soon: false, past: true };
      return { txt: 'in ' + days + ' day' + (days === 1 ? '' : 's'), soon: days <= 14, past: false };
    }
    if (it.month) {
      const [y, m] = it.month.split('-').map(Number);
      const cur = t.getFullYear() * 12 + t.getMonth(), tgt = y * 12 + (m - 1);
      if (tgt === cur) return { txt: 'this month', soon: true, past: false };
      if (tgt < cur) return { txt: 'month passed', soon: false, past: true };
      return { txt: 'in ' + (tgt - cur) + ' mo', soon: false, past: false };
    }
    if (it.season) return { txt: it.season, soon: false, past: false };
    return { txt: '', soon: false, past: false };
  }
  function itemHTML(it, gameKey, showGame) {
    const rel = relLabel(it), b = BASIS[it.basis] || [it.basis, ''];
    const g = R.games[gameKey] || {};
    return `<article class="rm-item${rel.past ? ' past' : ''}" data-basis="${esc(it.basis)}">
      <div class="rm-when">${esc(whenLabel(it))}<span class="rel${rel.soon ? ' soon' : ''}">${esc(rel.txt)}</span></div>
      <div><h3>${showGame ? `<span class="tag gray">${esc(g.short || gameKey.toUpperCase())}</span>` : ''}${esc(it.title)} <span class="basis ${esc(it.basis)}" title="${esc(b[1])}">${esc(b[0])}</span>${it.kind ? ` <span class="dim" style="font-size:12px;font-weight:500">${esc(it.kind)}</span>` : ''}</h3>
      <p>${esc(it.details)}</p>${it.dateNote ? `<p><b>${esc(it.dateNote)}</b></p>` : ''}${it.market ? `<p class="mkt">${esc(it.market)}</p>` : ''}
      <div class="rm-src">Source${it.src.length > 1 ? 's' : ''}: ${it.src.map(s => `<a href="${esc(s.u)}" target="_blank" rel="noopener">${esc(s.t)}</a>`).join('')}</div></div>
    </article>`;
  }
  function legendHTML() {
    return '<div class="rm-legend">' + Object.entries(BASIS).map(([k, v]) => `<span><span class="basis ${k}">${esc(v[0])}</span> ${esc(v[1])}</span>`).join('') + '</div>';
  }
  function sorted(gameKey) { return [...((R.games[gameKey] || {}).items || [])].sort((a, b) => sortKey(a) - sortKey(b)); }
  // Render one game's roadmap into el. opts.hideReleased hides already-released items by default (toggle shown).
  function render(el, gameKey, opts = {}) {
    const g = R.games[gameKey]; if (!el) return;
    if (!g) { el.innerHTML = '<div class="empty">Roadmap data missing (data/roadmaps.js).</div>'; return; }
    const id = 'rmx-' + gameKey;
    el.innerHTML = `<p class="note">What Jagex has announced, newest plans first by date. Exact days appear only where an official source gives one; everything else shows the window the source gives. Checked <b>${esc(R.checkedAt)}</b>. Roadmap pages: ${g.roadmapPages.map(p => `<a href="${esc(p.u)}" target="_blank" rel="noopener">${esc(p.t)}</a>`).join(' · ')}.</p>
      ${legendHTML()}
      <label class="chk rm-filter" style="display:inline-flex;gap:6px;align-items:center;font-size:12px;color:var(--mute)"><input type="checkbox" id="${id}" ${opts.hideReleased === false ? '' : 'checked'}> Hide released items</label>
      <div class="rm"></div>`;
    const list = el.querySelector('.rm'), cb = el.querySelector('#' + id);
    const draw = () => { list.innerHTML = sorted(gameKey).filter(it => !(cb.checked && it.basis === 'released')).map(it => itemHTML(it, gameKey)).join(''); };
    cb.addEventListener('change', draw); draw();
  }
  // Next dated, not-yet-past items across games (for the hub).
  function upcoming(keys, n = 8) {
    const t = today().getTime(), out = [];
    for (const k of keys) for (const it of ((R.games[k] || {}).items || [])) {
      if (it.basis === 'released') continue;
      const s = sortKey(it); if (!isFinite(s)) continue;
      if (it.date ? parseDay(it.date).getTime() < t : (relLabel(it).past)) continue;
      out.push({ k, it, s });
    }
    return out.sort((a, b) => a.s - b.s).slice(0, n);
  }
  window.RVRoadmap = { render, upcoming, itemHTML, whenLabel, relLabel, legendHTML, sortKey, data: R };
})();
