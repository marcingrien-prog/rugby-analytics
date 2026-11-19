(() => {
  'use strict';

  const TEAMS = [
    {id:'RSA',name:'RPA',elo:1900,attack:2.9,defence:1.9},
    {id:'NZL',name:'Nowa Zelandia',elo:1885,attack:3.0,defence:2.0},
    {id:'IRE',name:'Irlandia',elo:1860,attack:2.7,defence:1.8},
    {id:'FRA',name:'Francja',elo:1850,attack:2.8,defence:2.1},
    {id:'ENG',name:'Anglia',elo:1810,attack:2.5,defence:2.0},
    {id:'SCO',name:'Szkocja',elo:1760,attack:2.6,defence:2.3},
    {id:'ARG',name:'Argentyna',elo:1750,attack:2.4,defence:2.1},
    {id:'AUS',name:'Australia',elo:1725,attack:2.5,defence:2.5},
    {id:'WAL',name:'Walia',elo:1700,attack:2.2,defence:2.4},
    {id:'FIJ',name:'Fidżi',elo:1690,attack:2.7,defence:2.8},
    {id:'ITA',name:'Włochy',elo:1650,attack:2.3,defence:2.7},
    {id:'JPN',name:'Japonia',elo:1640,attack:2.5,defence:2.8}
  ];

  const $ = id => document.getElementById(id);
  const titles = {dashboard:'Panel główny',predictor:'Prognozator',teams:'Reprezentacje',worldcup:'Rugby World Cup',methodology:'Metodologia'};

  function showView(name) {
    if (!titles[name]) return;
    document.querySelectorAll('.view').forEach(el => el.classList.toggle('active', el.id === 'view-' + name));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === name));
    if ($('page-title')) $('page-title').textContent = titles[name];
    window.scrollTo(0, 0);
  }

  function fillTeams() {
    ['home','away'].forEach((id, index) => {
      const select = $(id);
      if (!select) return;
      select.replaceChildren(...TEAMS.map(team => {
        const option = document.createElement('option');
        option.value = team.id;
        option.textContent = team.name;
        return option;
      }));
      select.value = index === 0 ? 'NZL' : 'IRE';
    });
    const table = $('teams-table');
    if (table) {
      table.innerHTML = TEAMS.slice().sort((a,b) => b.elo-a.elo).map(t =>
        '<tr><td>' + t.name + ' <span class="tag">' + t.id + '</span></td><td><b>' + t.elo +
        '</b></td><td>Atak ' + t.attack.toFixed(1) + ' · Obrona ' + t.defence.toFixed(1) +
        '</td><td><span class="tag">PRIOR DEMO</span></td></tr>'
      ).join('');
    }
  }

  function poisson(mean) {
    const limit = Math.exp(-mean);
    let product = 1, count = 0;
    do { count++; product *= Math.random(); } while (product > limit && count < 30);
    return count - 1;
  }

  function simulateScore(team, opponent, eloAdjustment) {
    const triesMean = Math.max(0.2, team.attack * (opponent.defence / 2.3) * Math.exp(eloAdjustment / 1800));
    const penaltiesMean = Math.max(0.2, 0.95 * (1 + Math.max(-0.2, Math.min(0.2, (opponent.elo-team.elo)/400))));
    const tries = poisson(triesMean);
    let points = tries * 5;
    for (let i=0; i<tries; i++) if (Math.random() < 0.78) points += 2;
    points += poisson(penaltiesMean) * 3;
    return points;
  }

  function predict() {
    const a = TEAMS.find(t => t.id === $('home').value);
    const b = TEAMS.find(t => t.id === $('away').value);
    const result = $('prediction-result');
    if (!a || !b || !result) return;
    if (a.id === b.id) {
      result.innerHTML = '<div class="empty-state"><h3>Wybierz dwie różne drużyny</h3></div>';
      return;
    }
    const venue = $('venue').value;
    const simulations = Number($('n-sims').value) || 5000;
    const adjustment = venue === 'home' ? 55 : venue === 'away' ? -55 : 0;
    const difference = a.elo + adjustment - b.elo;
    let winsA=0, winsB=0, draws=0, totalA=0, totalB=0;
    const scoreCounts = {};
    for (let i=0; i<simulations; i++) {
      const scoreA = simulateScore(a,b,difference/2);
      const scoreB = simulateScore(b,a,-difference/2);
      totalA += scoreA; totalB += scoreB;
      if (scoreA > scoreB) winsA++; else if (scoreB > scoreA) winsB++; else draws++;
      const key = scoreA + ':' + scoreB;
      scoreCounts[key] = (scoreCounts[key] || 0) + 1;
    }
    const pct = value => (100*value/simulations).toFixed(1);
    const averageA = totalA/simulations, averageB = totalB/simulations;
    const mostCommon = Object.entries(scoreCounts).sort((x,y)=>y[1]-x[1])[0][0];
    result.innerHTML =
      '<div class="result-head"><h3>Wynik symulacji</h3><span class="tag">' + simulations.toLocaleString('pl-PL') + ' symulacji</span></div>' +
      '<div class="scoreline"><div><span>' + a.name + '</span><br><strong>' + averageA.toFixed(0) + '</strong></div><span>ŚREDNIA<br>PROGNOZA</span><div><span>' + b.name + '</span><br><strong>' + averageB.toFixed(0) + '</strong></div></div>' +
      '<div class="win-grid"><div class="win-box"><b>' + pct(winsA) + '%</b><span>Wygrana ' + a.id + '</span></div><div class="win-box"><b>' + pct(draws) + '%</b><span>Remis</span></div><div class="win-box"><b>' + pct(winsB) + '%</b><span>Wygrana ' + b.id + '</span></div></div>' +
      '<div class="bar-label"><span>' + a.name + '</span><b>' + pct(winsA) + '%</b></div><div class="bar"><div class="a" style="width:' + pct(winsA) + '%"></div><div class="b" style="width:' + pct(winsB) + '%"></div></div>' +
      '<div class="bar-label"><span>' + b.name + '</span><b>' + pct(winsB) + '%</b></div>' +
      '<p class="fine">Najczęściej wylosowany dokładny wynik: <b>' + mostCommon + '</b>. Oczekiwana różnica punktów: <b>' + (averageA-averageB).toFixed(1) + '</b>.</p>' +
      '<div class="notice"><b>Interpretacja</b><p>Symulacja korzysta z przykładowych parametrów drużyn. To prototyp, nie zweryfikowana prognoza.</p></div>';
  }

  function init() {
    document.addEventListener('click', event => {
      const nav = event.target.closest('[data-view]');
      const go = event.target.closest('[data-go]');
      if (nav) showView(nav.dataset.view);
      if (go) showView(go.dataset.go);
    });
    fillTeams();
    const runButton = $('run-prediction');
    if (runButton) runButton.addEventListener('click', predict);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
  window.RugbyAnalytics = {version:'0.2.0', teams:TEAMS.length};
})();