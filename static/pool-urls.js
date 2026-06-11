/** Safe pool URL builders (invite codes may contain digits). */
(function (global) {
  function poolCode() {
    return document.body?.dataset?.poolCode || '';
  }

  function teamSlugs() {
    try {
      return JSON.parse(document.body?.dataset?.teamSlugs || '{}');
    } catch (_) {
      return {};
    }
  }

  global.poolMatchUrl = function (matchId) {
    const code = poolCode();
    if (!code || matchId == null) return '#';
    return `/pool/${encodeURIComponent(code)}/match/${matchId}`;
  };

  global.poolTeamUrl = function (teamName) {
    const code = poolCode();
    const slug = teamSlugs()[teamName];
    if (!code || !slug) return null;
    return `/pool/${encodeURIComponent(code)}/team/${slug}`;
  };

  global.poolPlayerUrl = function (userId) {
    const code = poolCode();
    if (!code || userId == null) return '#';
    return `/pool/${encodeURIComponent(code)}/player/${userId}`;
  };

  global.sanitizeMinuteLabel = function (label) {
    if (!label) return 'LIVE';
    const text = String(label).trim();
    if (text === '0' || text === "0'") return 'LIVE';
    return text;
  };

  global.sanitizeGoalMinute = function (label) {
    if (!label) return '—';
    const text = String(label).trim();
    if (text === '0' || text === "0'") return '—';
    return text;
  };

  global.renderGoalsHtml = function (goals, compact) {
    if (!goals || !goals.length) return '';
    const home = goals
      .filter(g => g.team_side === 'home')
      .map(g => {
        const min = sanitizeGoalMinute(g.minute_label);
        const pen = g.is_penalty ? ' <span class="pen-tag">(pen)</span>' : '';
        return `<div class="goal-event"><span class="goal-minute">${min}</span><span class="goal-player">${g.scorer_name}${pen}</span></div>`;
      })
      .join('');
    const away = goals
      .filter(g => g.team_side === 'away')
      .map(g => {
        const min = sanitizeGoalMinute(g.minute_label);
        const pen = g.is_penalty ? ' <span class="pen-tag">(pen)</span>' : '';
        return `<div class="goal-event"><span class="goal-minute">${min}</span><span class="goal-player">${g.scorer_name}${pen}</span></div>`;
      })
      .join('');
    const cls = compact ? 'goal-scorers goal-scorers-compact' : 'goal-scorers';
    return `<div class="${cls}"><div class="goal-column goal-home">${home}</div><div class="goal-column goal-away">${away}</div></div>`;
  };

  global.renderCardsHtml = function (cards, compact) {
    if (!cards || !cards.length) return '';
    const cls = compact ? 'match-card-events match-card-events-compact' : 'match-card-events';
    const items = cards.map(c => {
      const icon = c.card_type === 'red' ? '🟥' : '🟨';
      const min = sanitizeGoalMinute(c.minute_label);
      const minHtml = min !== '—' ? `<span class="card-minute">${min}</span>` : '';
      return `<div class="card-event card-event-${c.card_type}"><span class="card-icon">${icon}</span>${minHtml}<span class="card-player">${c.player_name}</span><span class="card-team">(${c.team})</span></div>`;
    }).join('');
    return `<div class="${cls}">${items}</div>`;
  };
})(window);
