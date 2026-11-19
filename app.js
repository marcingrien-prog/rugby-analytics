(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const titles = {dashboard:'Nadchodzące mecze',predictor:'Prognozator',teams:'Reprezentacje',worldcup:'Rugby World Cup',methodology:'Metodologia'};
  const TEAMS = [
    ['RSA','RPA',1900],['NZL','Nowa Zelandia',1885],['IRE','Irlandia',1860],
    ['FRA','Francja',1850],['ENG','Anglia',1810],['SCO','Szkocja',1760],
    ['ARG','Argentyna',1750],['AUS','Australia',1725],['WAL','Walia',1700],
    ['FIJ','Fidżi',1690],['ITA','Włochy',1650],['JPN','Japonia',1640]
  ];
  let liveData = null;

  function showView(name) {
    if (!titles[name]) return;
    document.querySelectorAll('.view').forEach(el => el.classList.toggle('active', el.id === 'view-' + name));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === name));
    if ($('page-title')) $('page-title').textContent = titles[name];
    window.scrollTo(0, 0);
  }

  function fillTeams() {
    const table = $('teams-table');
    if (!table) return;
    table.innerHTML = TEAMS.slice().sort((a,b) => b[2]-a[2]).map(t =>
      '<tr><td>' + t[1] + ' <span class="tag">' + t[0] + '</span></td><td><b>' + t[2] +
      '</b></td><td>Wartość demonstracyjna</td><td><span class="tag">DEMO</span></td></tr>'
    ).join('');
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function formatDate(match) {
    const value = match.kickoff_utc || match.date;
    if (!value) return 'Termin nieustalony';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return escapeHtml(match.date);
    return new Intl.DateTimeFormat('pl-PL', {
      weekday:'short', day:'2-digit', month:'2-digit', year:'numeric',
      hour: match.kickoff_utc ? '2-digit' : undefined,
      minute: match.kickoff_utc ? '2-digit' : undefined,
      timeZone:'Europe/Warsaw'
    }).format(date);
  }

  function renderFixtures() {
    const list = $('fixtures-list');
    const status = $('fixtures-status');
    if (!list || !status) return;
    if (!liveData || !Array.isArray(liveData.fixtures)) {
      status.innerHTML = '<b>Nie udało się pobrać terminarza.</b><p>Automatyczna aktualizacja danych jeszcze się nie zakończyła. Spróbuj ponownie później.</p>';
      list.innerHTML = '';
      return;
    }
    const fixtures = liveData.fixtures;
    status.innerHTML = '<b>Źródło danych: rugbyAPI · ' + fixtures.length + ' spotkań</b><p>Zakres: najbliższe ' +
      escapeHtml(liveData.window_days || 60) + ' dni. Ostatnia aktualizacja: ' +
      escapeHtml(new Date(liveData.generated_at).toLocaleString('pl-PL')) +
      '. Terminarz odświeża się automatycznie dwa razy dziennie.</p>';
    if (!fixtures.length) {
      list.innerHTML = '<div class="panel empty-state"><h3>Brak zaplanowanych spotkań</h3><p>W źródle nie ma obecnie nadchodzących meczów w wybranym zakresie.</p></div>';
      return;
    }
    list.innerHTML = fixtures.map(match => {
      const prediction = match.prediction;
      const analysis = prediction
        ? '<div class="fixture-prob"><div><b>' + prediction.home_win + '%</b><span>Wygrana gospodarzy</span></div><div><b>' +
          prediction.draw + '%</b><span>Remis</span></div><div><b>' + prediction.away_win +
          '%</b><span>Wygrana gości</span></div></div><p class="fixture-basis">Prognoza wstępna na podstawie: ' +
          escapeHtml(match.prediction_basis || 'dostępnych danych') +
          (prediction.home_score !== null && prediction.away_score !== null
            ? ' · orientacyjny wynik: ' + prediction.home_score + '–' + prediction.away_score : '') +
          '</p>'
        : '<p class="fixture-basis no-prediction">Brak wystarczających danych do odpowiedzialnego wyliczenia prawdopodobieństwa dla obu drużyn. Nie pokazujemy fikcyjnych procentów.</p>';
      return '<article class="fixture-card"><div class="fixture-meta"><span>' +
        escapeHtml(match.competition) + '</span><time>' + formatDate(match) +
        '</time></div><div class="fixture-teams"><div><small>GOSPODARZE</small><strong>' +
        escapeHtml(match.home?.name) + '</strong></div><span class="fixture-vs">VS</span><div class="away"><small>GOŚCIE</small><strong>' +
        escapeHtml(match.away?.name) + '</strong></div></div>' + analysis + '</article>';
    }).join('');
  }

  async function loadFixtures() {
    const status = $('fixtures-status');
    if (status) status.innerHTML = '<b>Aktualizuję terminarz…</b><p>Pobieram ostatnią opublikowaną paczkę danych.</p>';
    try {
      const response = await fetch('./data/live-data.json?v=' + Date.now(), {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      liveData = await response.json();
      renderFixtures();
    } catch (error) {
      liveData = null;
      renderFixtures();
      console.error('Rugby Analytics data load failed:', error);
    }
  }

  function init() {
    document.addEventListener('click', event => {
      const nav = event.target.closest('[data-view]');
      const go = event.target.closest('[data-go]');
      if (nav) showView(nav.dataset.view);
      else if (go) showView(go.dataset.go);
      if (event.target.closest('#refresh-fixtures')) loadFixtures();
    });
    fillTeams();
    loadFixtures();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
  window.RugbyAnalytics = {version:'0.3.0', dataMode:'scheduled-static-feed'};
})();