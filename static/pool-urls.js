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

  global.deriveLiveMinuteFromKickoff = function (kickoffIso) {
    if (!kickoffIso) return null;
    const kickoff = new Date(kickoffIso);
    if (Number.isNaN(kickoff.getTime())) return null;
    const elapsedMins = Math.floor((Date.now() - kickoff.getTime()) / 60000);
    if (elapsedMins <= 45) return `${Math.max(1, elapsedMins)}'`;
    if (elapsedMins <= 60) return 'HT';
    return `${Math.min(90, 45 + elapsedMins - 60)}'`;
  };

  global.resolveLiveMinuteLabel = function (minuteLabel, kickoffIso, status) {
    const cleaned = sanitizeMinuteLabel(minuteLabel);
    if (status === 'halftime' || cleaned.startsWith('HT')) {
      return cleaned.startsWith('HT') ? cleaned : 'HT';
    }
    // Trust server-synced minute from ESPN/API polling.
    if (cleaned && cleaned !== 'LIVE' && cleaned.endsWith("'")) {
      return cleaned;
    }
    const derived = deriveLiveMinuteFromKickoff(kickoffIso);
    if (derived === 'HT') return 'HT';
    if (cleaned === "45'" || cleaned === 'LIVE' || !minuteLabel) {
      return derived || cleaned;
    }
    return cleaned;
  };

  global.sanitizeMinuteLabel = function (label) {
    if (!label) return 'LIVE';
    const text = String(label).trim();
    if (text === '0' || text === "0'") return 'LIVE';
    if (text.startsWith('HT')) return text;
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
        const pen = g.is_penalty ? ' <span class="pen-tag">(pen)</span>' : '';
        return `<div class="goal-event"><span class="goal-minute">${sanitizeGoalMinute(g.minute_label)}</span><span class="goal-player">${g.scorer_name}${pen}</span></div>`;
      })
      .join('');
    const away = goals
      .filter(g => g.team_side === 'away')
      .map(g => {
        const pen = g.is_penalty ? ' <span class="pen-tag">(pen)</span>' : '';
        return `<div class="goal-event"><span class="goal-minute">${sanitizeGoalMinute(g.minute_label)}</span><span class="goal-player">${g.scorer_name}${pen}</span></div>`;
      })
      .join('');
    const compactClass = compact ? ' goal-scorers-compact' : '';
    return `<div class="goal-scorers${compactClass}"><div class="goal-column goal-home">${home}</div><div class="goal-column goal-away">${away}</div></div>`;
  };

  global.renderCardsHtml = function (cards, compact) {
    if (!cards || !cards.length) return '';
    const compactClass = compact ? ' match-cards-compact' : '';
    const items = cards.map(c => {
      const icon = c.card_type === 'red' ? '🟥' : '🟨';
      return `<div class="card-event card-${c.card_type}"><span class="card-icon">${icon}</span><span class="goal-minute">${sanitizeGoalMinute(c.minute_label)}</span><span class="card-player">${c.player_name}</span></div>`;
    }).join('');
    return `<div class="match-cards${compactClass}" data-match-cards>${items}</div>`;
  };

  global.renderMatchEventsHtml = function (goals, cards, compact) {
    return `${renderGoalsHtml(goals, compact)}${renderCardsHtml(cards, compact)}`;
  };
})(window);
