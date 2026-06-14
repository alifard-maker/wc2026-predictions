/** Format pool kickoffs/deadlines in the viewer's local timezone (rules stay ET on server). */
(function (global) {
  const POOL_ET = 'America/New_York';
  const OVERRIDE_KEY = 'wc2026_tz_override';

  function parseInstant(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function readUrlTzOverride() {
    try {
      const params = new URLSearchParams(global.location.search);
      const tz = params.get('tz');
      if (tz) {
        global.sessionStorage.setItem(OVERRIDE_KEY, tz);
        return tz;
      }
    } catch (_) { /* ignore */ }
    return null;
  }

  function getDisplayTimezone() {
    const fromUrl = readUrlTzOverride();
    if (fromUrl) return fromUrl;
    try {
      const stored = global.sessionStorage.getItem(OVERRIDE_KEY);
      if (stored) return stored;
    } catch (_) { /* ignore */ }
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || POOL_ET;
    } catch (_) {
      return POOL_ET;
    }
  }

  function formatParts(iso, tz, options) {
    const d = parseInstant(iso);
    if (!d) return null;
    try {
      return new Intl.DateTimeFormat('en-GB', { timeZone: tz, ...options }).formatToParts(d);
    } catch (_) {
      return null;
    }
  }

  function tzAbbr(iso, tz) {
    const parts = formatParts(iso, tz, { timeZoneName: 'short' });
    if (!parts) return tz;
    return parts.find(p => p.type === 'timeZoneName')?.value || tz;
  }

  function formatInZone(iso, tz, options) {
    const d = parseInstant(iso);
    if (!d) return '';
    try {
      return new Intl.DateTimeFormat('en-GB', { timeZone: tz, ...options }).format(d);
    } catch (_) {
      return '';
    }
  }

  const FORMATS = {
    'kickoff-long': {
      weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false,
    },
    'kickoff-short': {
      weekday: 'short', day: 'numeric', month: 'short',
      hour: '2-digit', minute: '2-digit', hour12: false,
    },
    'deadline-short': {
      weekday: 'short', day: 'numeric', month: 'short',
      hour: '2-digit', minute: '2-digit', hour12: false,
    },
    'deadline-long': {
      weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false,
    },
  };

  function formatLocal(iso, formatName) {
    const opts = FORMATS[formatName] || FORMATS['kickoff-long'];
    const tz = getDisplayTimezone();
    const text = formatInZone(iso, tz, opts);
    if (!text) return '';
    const abbr = tzAbbr(iso, tz);
    return `${text} ${abbr}`.trim();
  }

  function formatEt(iso, formatName) {
    const opts = FORMATS[formatName] || FORMATS['kickoff-short'];
    const text = formatInZone(iso, POOL_ET, opts);
    return text ? `${text} ET` : '';
  }

  function escapeHtml(text) {
    const d = global.document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }

  function formatWithEtRef(iso, formatName, showEt) {
    const local = formatLocal(iso, formatName);
    if (!local) return { html: '', text: '' };
    const tz = getDisplayTimezone();
    if (!showEt || tz === POOL_ET) {
      return { html: escapeHtml(local), text: local };
    }
    const et = formatEt(iso, formatName);
    if (!et) {
      return { html: escapeHtml(local), text: local };
    }
    return {
      html: `${escapeHtml(local)} <span class="local-time-et-ref">(${escapeHtml(et)})</span>`,
      text: `${local} (${et})`,
    };
  }

  function applyElement(el) {
    const iso = el.dataset.localTime || el.dataset.localDeadline || el.dataset.deadline;
    if (!iso) return;

    const format = el.dataset.localFormat || 'kickoff-long';
    const showEt = el.dataset.showEt !== 'false';
    const teams = el.dataset.localBannerTeams;

    if (format === 'banner' && teams) {
      const { html } = formatWithEtRef(iso, 'kickoff-short', showEt);
      el.innerHTML = `${escapeHtml(teams)} · ${html}`;
      return;
    }

    const prefix = el.dataset.localDeadlinePrefix || el.dataset.localPrefix;
    const { html, text } = formatWithEtRef(iso, format, showEt);

    if (prefix) {
      el.innerHTML = `${escapeHtml(prefix)} ${html}`;
    } else if (el.dataset.localHtml === 'true') {
      el.innerHTML = html;
    } else {
      el.textContent = prefix ? `${prefix} ${text}` : text;
    }
  }

  function applyLocalTimes(root) {
    const scope = root || global.document;
    scope.querySelectorAll('[data-local-time], [data-local-deadline]').forEach(applyElement);
    scope.querySelectorAll('.badge-deadline-track[data-deadline]:not([data-local-skip])').forEach(el => {
      if (el.dataset.localDeadlinePrefix === undefined) {
        el.dataset.localDeadlinePrefix = 'Open until';
      }
      el.dataset.localDeadline = el.dataset.deadline;
      el.dataset.localFormat = el.dataset.localFormat || 'deadline-short';
      applyElement(el);
    });
    scope.querySelectorAll('[data-local-kickoff-line]').forEach(el => {
      el.dataset.localFormat = el.dataset.localFormat || 'kickoff-short';
      applyElement(el);
    });
  }

  function timezoneHintText() {
    const tz = getDisplayTimezone();
    let label;
    try {
      label = new Intl.DateTimeFormat('en', { timeZone: tz, timeZoneName: 'long' }).formatToParts(new Date())
        .find(p => p.type === 'timeZoneName')?.value || tz;
    } catch (_) {
      label = tz;
    }
    const override = (() => {
      try { return global.sessionStorage.getItem(OVERRIDE_KEY); } catch (_) { return null; }
    })();
    if (override) {
      return `Times shown in ${label} (test override — add ?tz= to change)`;
    }
    if (tz === POOL_ET) {
      return 'Times shown in Eastern Time';
    }
    return `Times in your timezone (${label}) · ET shown in parentheses`;
  }

  function renderTimezoneHint() {
    const el = global.document.getElementById('local-timezone-hint');
    if (el) el.textContent = timezoneHintText();
  }

  function initLocalTimes() {
    applyLocalTimes();
    renderTimezoneHint();
  }

  global.POOL_ET = POOL_ET;
  global.getDisplayTimezone = getDisplayTimezone;
  global.formatLocalDateTime = formatLocal;
  global.formatLocalWithEtRef = formatWithEtRef;
  global.applyLocalTimes = applyLocalTimes;
  global.initLocalTimes = initLocalTimes;
  global.formatDeadlineLabel = function (iso, prefix) {
    const { text } = formatWithEtRef(iso, 'deadline-short', true);
    return prefix ? `${prefix} ${text}` : text;
  };

  if (global.document.readyState === 'loading') {
    global.document.addEventListener('DOMContentLoaded', initLocalTimes);
  } else {
    initLocalTimes();
  }
})(window);
