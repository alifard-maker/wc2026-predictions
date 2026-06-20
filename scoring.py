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


def bold_day_key(match: dict) -> str:
    """One bold pick per calendar day (ET), keyed by match_date."""
    date = match.get("match_date") or match.get("date")
    if date:
        return f"day_{date}"
    if match.get("matchday"):
        return f"md{match['matchday']}"
    return f"ko_{match.get('stage') or 'knockout'}"


def bold_pick_change_allowed(
    target_match: dict,
    existing_bold_match: dict | None,
) -> bool:
    """True when the user may set or move their bold pick to target_match."""
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
    return " ".join(name.strip().lower().split())


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

    if results.get("winner") and vote.get("winner") == results["winner"]:
        breakdown["winner"] = TOURNAMENT_WINNER_PTS
    if results.get("second_place") and vote.get("second_place") == results["second_place"]:
        breakdown["second_place"] = TOURNAMENT_SECOND_PTS
    if results.get("third_place") and vote.get("third_place") == results["third_place"]:
        breakdown["third_place"] = TOURNAMENT_THIRD_PTS
    if results.get("top_scorer") and normalize_player(vote.get("top_scorer", "")) == normalize_player(
        results["top_scorer"]
    ):
        breakdown["top_scorer"] = TOURNAMENT_TOP_SCORER_PTS

    breakdown["total"] = sum(breakdown[k] for k in ("winner", "second_place", "third_place", "top_scorer"))
    return breakdown


def calculate_points(
    pred_home: int,
    pred_away: int,
    actual_home: int | None,
    actual_away: int | None,
    is_bold: bool = False,
) -> int | None:
    if actual_home is None or actual_away is None:
        return None
    if pred_home == actual_home and pred_away == actual_away:
        base = 5
    elif match_result(pred_home, pred_away) == match_result(actual_home, actual_away):
        base = 2
    else:
        base = 0
    if is_bold and base > 0:
        return base * 2
    return base
