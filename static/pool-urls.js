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
    const elapsedMs = Date.now() - kickoff.getTime();
    if (elapsedMs <= 0) return null;
    const elapsedMins = Math.floor(elapsedMs / 60000);
    if (elapsedMins <= 0) return "1'";
    if (elapsedMins <= 45) return `${elapsedMins}'`;
    if (elapsedMins <= 60) return 'HT';
    return `${Math.min(90, 45 + elapsedMins - 60)}'`;
  };

  global.resolveLiveMinuteLabel = function (minuteLabel, kickoffIso, status) {
    const cleaned = sanitizeMinuteLabel(minuteLabel);
    if (kickoffIso) {
      const kickoff = new Date(kickoffIso);
      if (!Number.isNaN(kickoff.getTime()) && Date.now() < kickoff.getTime()) {
        return 'Soon';
      }
    }
    if (status === 'penalty_shootout') {
      return 'Pens';
    }
    if (status === 'extra_time') {
      const et = cleaned && cleaned !== 'LIVE' ? cleaned.replace(/^ET\s+/, '') : '';
      return et ? `ET ${et}` : 'ET';
    }
    if (status === 'halftime' || cleaned.startsWith('HT')) {
      return cleaned.startsWith('HT') ? cleaned : 'HT';
    }
    if (status === 'hydration_break' || cleaned.includes('Drinks break') || cleaned.startsWith('💧')) {
      return cleaned && cleaned !== 'LIVE' ? cleaned : '💧 Drinks break';
    }
    // Trust server-synced minute from ESPN/API polling, but never ahead of kickoff wall clock.
    if (cleaned && cleaned !== 'LIVE' && cleaned !== 'Soon' && cleaned.endsWith("'")) {
      if (/^\d+\+\d+'$/.test(cleaned)) {
        return cleaned;
      }
      const derived = deriveLiveMinuteFromKickoff(kickoffIso);
      if (derived && derived !== 'HT') {
        const shown = parseInt(cleaned, 10);
        const wall = parseInt(derived, 10);
        if (!Number.isNaN(shown) && !Number.isNaN(wall) && shown > wall) {
          return derived;
        }
      }
      return cleaned;
    }
    const derived = deriveLiveMinuteFromKickoff(kickoffIso);
    if (derived === 'HT') return 'HT';
    if (cleaned === "45'" || cleaned === 'LIVE' || !minuteLabel) {
      return derived || cleaned;
    }
    return cleaned;
  };

  global.formatLiveBannerMinute = function (commentary, escapeHtml) {
    const esc = escapeHtml || function (text) {
      return String(text);
    };
    return formatMatchStatusBadge(commentary, esc, commentary.kickoff_iso);
  };

  global.formatMatchStatusBadge = function (match, escapeHtml, kickoffIso) {
    const esc = escapeHtml || function (text) {
      return String(text);
    };
    const status = match.status;
    const label = match.minute_base || match.minute_label;
    const kickoff = kickoffIso || match.kickoff_iso;
    if (status === 'halftime' || String(label || '').startsWith('HT')) {
      return esc(resolveLiveMinuteLabel(label, kickoff, 'halftime'));
    }
    if (status === 'hydration_break' || String(label || '').includes('Drinks break')) {
      return esc(resolveLiveMinuteLabel(label, kickoff, 'hydration_break'));
    }
    if (status === 'penalty_shootout') {
      return esc('Pens');
    }
    if (status === 'extra_time') {
      const base = resolveLiveMinuteLabel(label, kickoff, 'extra_time');
      const added = match.added_time_label
        ? ` <span class="live-added-time">${esc(match.added_time_label)}</span>`
        : '';
      return `${esc(base)}${added}`;
    }
    const base = resolveLiveMinuteLabel(label, kickoff, status);
    const added = match.added_time_label
      ? ` <span class="live-added-time">${esc(match.added_time_label)}</span>`
      : '';
    return `LIVE ${esc(base)}${added ? ` ${added}` : ''}`;
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

  function cardSide(c, homeTeam, awayTeam) {
    if (c.team_side === 'home' || c.team === homeTeam) return 'home';
    if (c.team_side === 'away' || c.team === awayTeam) return 'away';
    return null;
  }

  global.renderCardsHtml = function (cards, compact, homeTeam, awayTeam) {
    if (!cards || !cards.length) return '';
    const compactClass = compact ? ' match-cards-compact' : '';
    const renderCol = (side) => cards
      .filter(c => cardSide(c, homeTeam, awayTeam) === side)
      .map(c => {
        const icon = c.card_type === 'red' ? '🟥' : '🟨';
        return `<div class="card-event card-${c.card_type}"><span class="card-icon">${icon}</span><span class="goal-minute">${sanitizeGoalMinute(c.minute_label)}</span><span class="card-player">${c.player_name}</span></div>`;
      })
      .join('');
    const homeTitle = !compact && homeTeam ? `<div class="card-column-title">${homeTeam}</div>` : '';
    const awayTitle = !compact && awayTeam ? `<div class="card-column-title">${awayTeam}</div>` : '';
    return `<div class="match-cards${compactClass}" data-match-cards><div class="card-column card-home">${homeTitle}${renderCol('home')}</div><div class="card-column card-away">${awayTitle}${renderCol('away')}</div></div>`;
  };

  global.renderPenaltiesHtml = function (penalties, compact, homeTeam, awayTeam) {
    const kicks = (penalties || []).filter(p => (p.minute || 0) > 120);
    if (!kicks.length) return '';
    const compactClass = compact ? ' match-shootout-compact' : '';
    const renderCol = (team) => kicks
      .filter(p => p.taker_team === team)
      .map(p => {
        const icon = p.outcome === 'scored' ? '✅' : p.outcome === 'saved' ? '🧤' : '❌';
        const player = p.taker_name || team;
        return `<div class="shootout-kick shootout-${p.outcome}"><span class="shootout-icon">${icon}</span><span class="shootout-player">${player}</span></div>`;
      })
      .join('');
    const homeTitle = !compact && homeTeam ? `<div class="shootout-column-title">${homeTeam}</div>` : '';
    const awayTitle = !compact && awayTeam ? `<div class="shootout-column-title">${awayTeam}</div>` : '';
    return `<div class="match-shootout${compactClass}" data-match-shootout><div class="shootout-title">Penalty shootout</div><div class="shootout-columns"><div class="shootout-column shootout-home">${homeTitle}${renderCol(homeTeam)}</div><div class="shootout-column shootout-away">${awayTitle}${renderCol(awayTeam)}</div></div></div>`;
  };

  global.renderMatchEventsHtml = function (goals, cards, compact, homeTeam, awayTeam, penalties) {
    return `${renderGoalsHtml(goals, compact)}${renderCardsHtml(cards, compact, homeTeam, awayTeam)}${renderPenaltiesHtml(penalties, compact, homeTeam, awayTeam)}`;
  };
})(window);
