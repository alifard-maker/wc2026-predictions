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
})(window);
