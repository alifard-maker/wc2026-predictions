from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/New_York")
PREDICTION_DEADLINE_BEFORE_KICKOFF = timedelta(hours=1)


def parse_match_datetime(date_str: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=TIMEZONE)


def prediction_deadline(date_str: str, time_str: str) -> datetime:
    """Predictions close 1 hour before kickoff (ET)."""
    kickoff = parse_match_datetime(date_str, time_str)
    return kickoff - PREDICTION_DEADLINE_BEFORE_KICKOFF


def is_prediction_open(date_str: str, time_str: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(TIMEZONE)
    return now <= prediction_deadline(date_str, time_str)


def match_result(home: int, away: int) -> str:
    if home > away:
        return "home"
    if home < away:
        return "away"
    return "draw"


OPENING_MATCH_DATE = "2026-06-11"
OPENING_MATCH_TIME = "15:00"
KNOCKOUT_TBD = "TBD"


def match_teams_known(home_team: str | None, away_team: str | None) -> bool:
    """True when both sides are confirmed (not placeholder TBD)."""
    unknown = {"", KNOCKOUT_TBD}
    return (home_team or "").strip() not in unknown and (away_team or "").strip() not in unknown


def tournament_vote_deadline() -> datetime:
    """Tournament votes lock 1 minute before the opening match kickoff."""
    kickoff = parse_match_datetime(OPENING_MATCH_DATE, OPENING_MATCH_TIME)
    return kickoff - timedelta(minutes=1)


def is_tournament_vote_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(TIMEZONE)
    return now < tournament_vote_deadline()


TOURNAMENT_WINNER_PTS = 50
TOURNAMENT_SECOND_PTS = 25
TOURNAMENT_THIRD_PTS = 15
TOURNAMENT_TOP_SCORER_PTS = 25

PHASE_BONUS_PTS = 15

KNOCKOUT_STAGES = frozenset({
    "round_of_32",
    "round_of_16",
    "quarter_final",
    "semi_final",
    "third_place",
    "final",
})

# From Round of 16 onward, users may predict a draw plus a penalty-shootout winner.
PENS_DRAW_STAGES = frozenset({
    "round_of_16",
    "quarter_final",
    "semi_final",
    "third_place",
    "final",
})


def is_knockout_stage(stage: str | None) -> bool:
    return (stage or "group") != "group"


def is_knockout_match(match) -> bool:
    return is_knockout_stage(match["stage"])


def is_knockout_no_draw_stage(stage: str | None) -> bool:
    """Round of 32 only — picks must have a winner in the scoreline."""
    return stage == "round_of_32"


def is_pens_draw_allowed_stage(stage: str | None) -> bool:
    """Round of 16+ — tied scorelines require a penalty-shootout winner pick."""
    return (stage or "") in PENS_DRAW_STAGES


def match_counts_by_date(matches) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in matches:
        date = m["match_date"]
        if date:
            counts[date] = counts.get(date, 0) + 1
    return counts


def bold_allowed_for_date(match_date: str | None, counts: dict[str, int] | None = None) -> bool:
    """Bold 2× only when more than one match is played on that calendar day (ET)."""
    if not match_date:
        return False
    if counts is None:
        return True
    return counts.get(match_date, 0) > 1


def validate_prediction_scores(
    home_score: int,
    away_score: int,
    stage: str | None,
    predicted_shootout_winner: str | None = None,
) -> str | None:
    if is_knockout_no_draw_stage(stage) and home_score == away_score:
        return (
            "Round of 32 picks must have a winner — draws are not allowed "
            "(extra time and penalties decide ties)."
        )
    if is_pens_draw_allowed_stage(stage) and home_score == away_score:
        if predicted_shootout_winner not in ("home", "away"):
            return (
                "Tied knockout picks need a penalty-shootout winner — "
                "choose which team advances after pens."
            )
    return None


def resolve_prediction_result(
    stage: str | None,
    pred_home: int,
    pred_away: int,
    predicted_shootout_winner: str | None = None,
) -> str:
    """Outcome implied by a prediction (pens winner when a draw is picked from R16+)."""
    if is_pens_draw_allowed_stage(stage) and pred_home == pred_away:
        if predicted_shootout_winner in ("home", "away"):
            return predicted_shootout_winner
        return "draw"
    return match_result(pred_home, pred_away)


def format_prediction_display(
    pred_home: int,
    pred_away: int,
    *,
    stage: str | None = None,
    predicted_shootout_winner: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> str:
    """Human-readable pick including pens winner when applicable."""
    line = f"{pred_home} – {pred_away}"
    if (
        is_pens_draw_allowed_stage(stage)
        and pred_home == pred_away
        and predicted_shootout_winner in ("home", "away")
        and home_team
        and away_team
    ):
        winner = home_team if predicted_shootout_winner == "home" else away_team
        line += f" ({winner} on pens)"
    return line


def bold_day_key(match) -> str:
    """One bold pick per calendar day (ET), keyed by match_date."""
    date = match["match_date"]
    if date:
        return f"day_{date}"
    if match["matchday"]:
        return f"md{match['matchday']}"
    return f"ko_{match['stage'] or 'knockout'}"


def bold_pick_change_allowed(
    target_match: dict,
    existing_bold_match: dict | None,
    *,
    matches_on_date: int,
) -> bool:
    """True when the user may set or move their bold pick to target_match."""
    if matches_on_date < 2:
        return False
    if not is_prediction_open(target_match["match_date"], target_match["match_time"]):
        return False
    if (
        existing_bold_match
        and existing_bold_match.get("id") != target_match.get("id")
        and not is_prediction_open(existing_bold_match["match_date"], existing_bold_match["match_time"])
    ):
        return False
    return True


def normalize_player(name: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.strip().lower().split())


def calculate_tournament_points(
    vote: dict | None,
    results: dict | None,
) -> dict:
    """Return breakdown and total bonus points from tournament picks."""
    breakdown = {
        "winner": 0,
        "second_place": 0,
        "third_place": 0,
        "top_scorer": 0,
        "total": 0,
    }
    if not vote or not results:
        return breakdown

    def _ready(value: str | None) -> str | None:
        text = (value or "").strip()
        if not text or text.upper() == "TBD":
            return None
        return text

    winner = _ready(results.get("winner"))
    second = _ready(results.get("second_place"))
    third = _ready(results.get("third_place"))
    scorer = _ready(results.get("top_scorer"))

    if winner and vote.get("winner") == winner:
        breakdown["winner"] = TOURNAMENT_WINNER_PTS
    if second and vote.get("second_place") == second:
        breakdown["second_place"] = TOURNAMENT_SECOND_PTS
    if third and vote.get("third_place") == third:
        breakdown["third_place"] = TOURNAMENT_THIRD_PTS
    pick = normalize_player(vote.get("top_scorer", ""))
    if pick:
        official = normalize_player(scorer) if scorer else ""
        if official and pick == official:
            breakdown["top_scorer"] = TOURNAMENT_TOP_SCORER_PTS
        elif not official or scorer is None:
            # Shared Golden Boot — award when the pick matches any co-leader.
            try:
                import db as _db

                co_leaders = {
                    normalize_player(name)
                    for name in _db.get_tournament_top_scorers()
                }
            except Exception:
                co_leaders = set()
            if pick in co_leaders:
                breakdown["top_scorer"] = TOURNAMENT_TOP_SCORER_PTS

    breakdown["total"] = sum(breakdown[k] for k in ("winner", "second_place", "third_place", "top_scorer"))
    return breakdown


def resolve_scoring_result(
    stage: str | None,
    actual_home: int,
    actual_away: int,
    shootout_winner: str | None = None,
) -> str:
    """Who won for points: knockout pens count; group stage uses the entered score."""
    if is_knockout_stage(stage) and shootout_winner in ("home", "away"):
        return shootout_winner
    return match_result(actual_home, actual_away)


def calculate_points(
    pred_home: int,
    pred_away: int,
    actual_home: int | None,
    actual_away: int | None,
    is_bold: bool = False,
    *,
    stage: str | None = None,
    shootout_winner: str | None = None,
    predicted_shootout_winner: str | None = None,
) -> int | None:
    if actual_home is None or actual_away is None:
        return None
    actual_result = resolve_scoring_result(stage, actual_home, actual_away, shootout_winner)
    pred_result = resolve_prediction_result(
        stage, pred_home, pred_away, predicted_shootout_winner
    )
    score_exact = pred_home == actual_home and pred_away == actual_away
    if (
        score_exact
        and is_pens_draw_allowed_stage(stage)
        and pred_home == pred_away
        and actual_result in ("home", "away")
    ):
        score_exact = predicted_shootout_winner == shootout_winner
    if score_exact:
        base = 5
    elif pred_result == actual_result:
        base = 2
    else:
        base = 0
    if is_bold and base > 0:
        return base * 2
    return base


def calculate_points_for_match(
    pred_home: int,
    pred_away: int,
    match,
    is_bold: bool = False,
    *,
    predicted_shootout_winner: str | None = None,
) -> int | None:
    """Score a prediction using a match row (sqlite3.Row or dict)."""
    shootout_winner = None
    if hasattr(match, "keys") and "shootout_winner" in match.keys():
        shootout_winner = match["shootout_winner"]
    return calculate_points(
        pred_home,
        pred_away,
        match["actual_home"],
        match["actual_away"],
        is_bold,
        stage=match["stage"],
        shootout_winner=shootout_winner,
        predicted_shootout_winner=predicted_shootout_winner,
    )
