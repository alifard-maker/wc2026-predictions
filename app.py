import json
import os
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix

import db
from ai_predictor import AI_AGENTS, AI_DISPLAY_NAME, ai_agent_badge, is_ai_agent
import live_score_sync
from live_scores import (
    apply_live_state,
    opening_kickoff_iso,
    sanitize_goal_minute_label,
    sanitize_minute_label,
)
from scoring import (
    PHASE_BONUS_PTS,
    TIMEZONE,
    TOURNAMENT_SECOND_PTS,
    TOURNAMENT_THIRD_PTS,
    TOURNAMENT_TOP_SCORER_PTS,
    TOURNAMENT_WINNER_PTS,
    calculate_tournament_points,
    is_prediction_open,
    is_tournament_vote_open,
    prediction_deadline,
    tournament_vote_deadline,
)
from player_stats import get_scorer_squads_data, get_scorer_status, resolve_scorer_pick_value
from team_data import get_match_context
from team_flags import get_flag_codes_for_js, get_flag_url
from prediction_simulation import build_predicted_tournament_view
from tournament_standings import build_tournament_view, tournament_view_for_json
from live_commentary import build_live_commentary, commentary_for_json
from match_spotlight import build_pool_spotlight, spotlight_for_json
from team_groups import get_group_preview
from team_history import get_coach_wc_record, get_team_history_bundle
from team_pool_stats import (
    get_team_live_tournament_stats,
    get_team_pool_prediction_stats,
    get_team_prediction_accuracy,
)
from team_profiles import get_team_profile, get_wc_titles, team_from_slug, team_slug
from teams import get_all_teams
from wc_news import get_wc_news, news_for_json
from engagement import (
    build_head_to_head,
    build_match_consensus,
    build_player_picks_summary,
    build_player_season_stats,
    filter_predictions_for_display,
    filter_ticker_predictions,
    filter_ticker_predictors,
    filter_tournament_votes_for_display,
    list_matchday_recaps,
    picks_revealed,
    tournament_picks_revealed,
)

APP_VERSION = "Beta 1.9"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
init_done = False


@app.template_filter("live_minute")
def live_minute_filter(value: str | None) -> str:
    return sanitize_minute_label(value)


@app.template_filter("goal_minute")
def goal_minute_filter(value: str | None) -> str:
    return sanitize_goal_minute_label(value)
MAINTENANCE_MODE = os.environ.get("MAINTENANCE_MODE", "").strip().lower() in ("1", "true", "yes")


def get_public_base_url() -> str:
    """Base URL for invite links. Set PUBLIC_URL when sharing outside this machine."""
    public = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if public:
        return public
    return request.host_url.rstrip("/")


def invite_url_for(invite_code: str) -> str:
    return get_public_base_url() + url_for("pool_join", invite_code=invite_code)


def comments_seen_key(pool_id: int) -> str:
    return f"comments_seen_{pool_id}"


def mark_comments_seen(pool_id: int) -> None:
    session[comments_seen_key(pool_id)] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def get_comments_seen(pool_id: int) -> str | None:
    return session.get(comments_seen_key(pool_id))


@app.context_processor
def inject_public_url():
    ctx = {
        "app_version": APP_VERSION,
        "public_base_url": lambda: get_public_base_url(),
        "invite_url_for": invite_url_for,
        "opening_kickoff_iso": opening_kickoff_iso(),
        "ai_display_name": AI_DISPLAY_NAME,
        "ai_agents": AI_AGENTS,
        "is_ai_agent": is_ai_agent,
        "ai_agent_badge": ai_agent_badge,
        "team_slug": team_slug,
        "flag_url": get_flag_url,
        "wc_titles": get_wc_titles,
        "match_spotlight": None,
        "live_commentary": None,
        "match_detail_url": match_detail_url,
        "team_page_url": team_page_url,
        "player_page_url": player_page_url,
        "team_slugs_json": json.dumps({t: team_slug(t) for t in get_all_teams()}),
    }
    pool_id = session.get("pool_id")
    if pool_id and session.get("user_id"):
        matches = enrich_matches(db.get_all_matches())
        ctx["match_spotlight"] = build_pool_spotlight(pool_id, matches)
        ctx["live_commentary"] = build_live_commentary(matches)
    return ctx


def ensure_db():
    global init_done
    if not init_done:
        db.init_db()
        db.ensure_ai_in_all_pools()
        init_done = True
    db.repair_live_display_data()


@app.before_request
def before_request():
    if request.path == "/health":
        return
    if MAINTENANCE_MODE and request.endpoint != "static":
        return render_template("maintenance.html"), 503
    ensure_db()


def match_detail_url(invite_code: str, match_id: int) -> str:
    return url_for("match_detail", invite_code=invite_code, match_id=match_id)


def team_page_url(invite_code: str, team_name: str) -> str:
    return url_for("team_page", invite_code=invite_code, team_slug_name=team_slug(team_name))


def player_page_url(invite_code: str, user_id: int) -> str:
    return url_for("player_page", invite_code=invite_code, user_id=user_id)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please join the pool first.", "error")
            invite_code = kwargs.get("invite_code")
            if invite_code:
                return redirect(url_for("pool_join", invite_code=invite_code))
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pool_id = session.get("pool_id")
        if not pool_id:
            flash("Pool access required.", "error")
            return redirect(url_for("index"))
        pool = db.get_pool_by_id(pool_id)
        if not pool or session.get("admin_secret") != pool["admin_secret"]:
            flash("Admin access required.", "error")
            return redirect(url_for("pool_dashboard", invite_code=pool["invite_code"] if pool else ""))
        return f(*args, **kwargs)

    return decorated


def goals_for_json(goals: list[dict]) -> list[dict]:
    return [
        {
            "team_side": g["team_side"],
            "scorer_name": g["scorer_name"],
            "minute_label": sanitize_goal_minute_label(g["minute_label"]),
            "team_name": g.get("team_name"),
            "is_penalty": bool(g.get("is_penalty")),
        }
        for g in goals
    ]


def cards_for_json(cards: list[dict]) -> list[dict]:
    return [
        {
            "player_name": c["player_name"],
            "team": c.get("team") or c.get("team_name"),
            "card_type": c["card_type"],
            "minute_label": sanitize_goal_minute_label(c.get("minute_label")),
        }
        for c in cards
    ]


def enrich_matches(matches, user_predictions=None):
    now = datetime.now(TIMEZONE)
    enriched = []
    for m in matches:
        d = apply_live_state(dict(m), now)
        d["deadline"] = prediction_deadline(m["match_date"], m["match_time"])
        d["open"] = is_prediction_open(m["match_date"], m["match_time"], now)
        d["deadline_urgent"] = (
            d["open"] and timedelta(0) < (d["deadline"] - now) <= timedelta(hours=1)
        )
        if user_predictions and m["id"] in user_predictions:
            pred = user_predictions[m["id"]]
            d["prediction"] = {
                "home_score": pred["home_score"],
                "away_score": pred["away_score"],
                "points": pred["points"],
                "submitted_at": pred["submitted_at"],
                "is_bold": bool(pred["is_bold"]) if "is_bold" in pred.keys() else False,
            }
        else:
            d["prediction"] = None
        d["goals"] = db.get_match_goals(m["id"])
        d["cards"] = db.get_match_cards(m["id"])
        d["penalties"] = db.get_match_penalties(m["id"])
        enriched.append(d)
    return enriched


def get_tournament_vote_status(user_id: int) -> dict:
    """Whether the user still needs tournament picks (scorer, winner, 2nd, 3rd)."""
    vote_open = is_tournament_vote_open()
    deadline = tournament_vote_deadline()
    vote = db.get_tournament_vote(user_id)
    fields = [
        ("top_scorer", "Top scorer"),
        ("winner", "Winner"),
        ("second_place", "2nd place"),
        ("third_place", "3rd place"),
    ]
    if vote:
        missing = [label for key, label in fields if not vote[key]]
    else:
        missing = [label for _, label in fields]
    submitted = len(missing) == 0
    return {
        "open": vote_open,
        "submitted": submitted,
        "show_reminder": vote_open and not submitted,
        "missing": missing,
        "deadline": deadline.isoformat(),
        "deadline_display": deadline.strftime("%a %d %b, %H:%M ET"),
    }


def find_next_prediction_needed(enriched_matches: list[dict]) -> dict | None:
    """Next open match the user has not predicted yet (soonest kickoff first)."""
    pending = [m for m in enriched_matches if m["open"] and not m.get("prediction")]
    if not pending:
        return None
    pending.sort(key=lambda m: m["kickoff"])
    m = pending[0]
    return {
        "match_id": m["id"],
        "home_team": m["home_team"],
        "away_team": m["away_team"],
        "kickoff": m["kickoff"].isoformat(),
        "deadline": m["deadline"].isoformat(),
        "deadline_display": m["deadline"].strftime("%a %d %b, %H:%M ET"),
    }


def _start_espn_sync_background() -> None:
    if os.environ.get("ESPN_SYNC_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        return

    def _loop() -> None:
        time.sleep(2)
        while True:
            try:
                live_score_sync._run_espn_sync()
            except Exception:
                pass
            time.sleep(int(os.environ.get("ESPN_SYNC_INTERVAL", "20")))

    threading.Thread(target=_loop, daemon=True, name="espn-live-sync").start()


def _start_live_sync_background() -> None:
    if os.environ.get("LIVE_SYNC_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        return
    if not live_score_sync.is_enabled():
        return

    def _loop() -> None:
        time.sleep(5)
        while True:
            try:
                live_score_sync.sync_live_scores()
            except Exception:
                pass
            time.sleep(live_score_sync.SYNC_COOLDOWN_SECONDS)

    threading.Thread(target=_loop, daemon=True, name="live-score-sync").start()


@app.route("/health")
def health():
    if MAINTENANCE_MODE:
        return jsonify({"status": "maintenance", "retry_minutes": 5}), 503
    try:
        ensure_db()
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 503
    payload = {
        "status": "ok",
        "version": APP_VERSION,
        "features": {
            "commentary_banner": True,
            "minute_fix": True,
            "api_live_clock": True,
            "halftime_countdown": True,
            "wc_competition_sync": True,
            "espn_events_sync": True,
        },
    }
    try:
        payload["live_sync"] = live_score_sync.get_sync_status()
    except Exception as exc:
        payload["live_sync"] = {"enabled": live_score_sync.is_enabled(), "error": str(exc)}
    try:
        import json

        espn_raw = db.get_sync_meta("espn_sync_summary")
        payload["espn_sync"] = json.loads(espn_raw) if espn_raw else None
        payload["espn_sync_error"] = db.get_sync_meta("espn_sync_error") or None
    except Exception:
        payload["espn_sync"] = None
        payload["espn_sync_error"] = None
    try:
        from datetime import datetime

        from live_scores import apply_live_state, minute_from_kickoff
        from scoring import TIMEZONE

        now = datetime.now(TIMEZONE)
        for row in db.get_all_matches():
            m = dict(row)
            if m.get("home_team") == "Mexico" and m.get("away_team") == "South Africa":
                enriched = apply_live_state(m, now)
                kickoff = enriched.get("kickoff")
                goals = db.get_match_goals(m["id"])
                payload["clock_debug"] = {
                    "db_live_minute": m.get("live_minute"),
                    "db_status": m.get("status"),
                    "live_home": m.get("live_home"),
                    "live_away": m.get("live_away"),
                    "minute_label": enriched.get("minute_label"),
                    "display_status": enriched.get("status"),
                    "kickoff_minute": minute_from_kickoff(kickoff, now) if kickoff else None,
                    "actual_home": m.get("actual_home"),
                    "goals_in_db": len(goals),
                    "goal_scorers": [g["scorer_name"] for g in goals],
                    "espn_source": db.get_sync_meta(f"espn_live_source_{m['id']}"),
                }
                break
    except Exception:
        pass
    return jsonify(payload)


ensure_db()


def _warm_live_data() -> None:
    try:
        live_score_sync._run_espn_sync()
    except Exception:
        pass


_warm_live_data()
_start_espn_sync_background()
_start_live_sync_background()


@app.route("/")
def index():
    return render_template("index.html", user=session.get("display_name"))


@app.route("/create", methods=["POST"])
def create_pool():
    name = request.form.get("pool_name", "").strip()
    if not name:
        flash("Pool name is required.", "error")
        return redirect(url_for("index"))

    pool = db.create_pool(name)
    db.ensure_all_ai_users(pool["id"])
    db.sync_ai_predictions(pool["id"])
    db.sync_ai_tournament_vote(pool["id"])
    session.clear()
    session["pool_id"] = pool["id"]
    session["invite_code"] = pool["invite_code"]
    session["admin_secret"] = pool["admin_secret"]
    flash(f"Pool created! Share this link with friends.", "success")
    return redirect(url_for("pool_join", invite_code=pool["invite_code"]))


@app.route("/join/<invite_code>", methods=["GET", "POST"])
def pool_join(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool:
        flash("Invalid invite link.", "error")
        return redirect(url_for("index"))

    session["pool_id"] = pool["id"]
    session["invite_code"] = invite_code

    if request.method == "POST":
        display_name = request.form.get("display_name", "")
        result = db.add_user(pool["id"], display_name)
        if isinstance(result, str):
            flash(result, "error")
        else:
            session["user_id"] = result["id"]
            session["display_name"] = result["display_name"]
            if result.get("resumed"):
                flash(
                    f"Welcome back, {result['display_name']}! Signed in to the existing account with this name.",
                    "success",
                )
            else:
                mark_comments_seen(pool["id"])
                flash(f"Welcome, {result['display_name']}!", "success")
            return redirect(url_for("pool_dashboard", invite_code=invite_code))

    user_count = db.count_pool_users(pool["id"])
    return render_template(
        "join.html",
        pool=pool,
        user_count=user_count,
        max_users=db.MAX_USERS_PER_POOL,
        logged_in=bool(session.get("user_id")),
        display_name=session.get("display_name"),
        existing_players=db.get_pool_users(pool["id"]),
    )


@app.route("/pool/<invite_code>")
@login_required
def pool_dashboard(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    db.sync_ai_predictions(pool["id"])
    db.sync_ai_tournament_vote(pool["id"])
    user_id = session["user_id"]
    matches = db.get_all_matches()
    predictions = db.get_user_predictions(user_id)
    enriched = enrich_matches(matches, predictions)
    leaderboard = db.get_leaderboard(pool["id"])

    open_count = sum(1 for m in enriched if m["open"])
    predicted_open = sum(1 for m in enriched if m["open"] and m["prediction"])
    next_prediction = find_next_prediction_needed(enriched)
    bold_by_day = db.get_user_bold_by_day(user_id)
    recaps = list_matchday_recaps(pool["id"])[:3]

    return render_template(
        "dashboard.html",
        pool=pool,
        matches=enriched,
        leaderboard=leaderboard,
        leader_message=db.get_leader_message(leaderboard),
        open_count=open_count,
        predicted_open=predicted_open,
        next_prediction=next_prediction,
        tournament_vote=get_tournament_vote_status(user_id),
        bold_by_day=bold_by_day,
        recaps=recaps,
        wc_news=get_wc_news(),
        is_admin=session.get("admin_secret") == pool["admin_secret"],
        invite_url=invite_url_for(invite_code),
    )


@app.route("/pool/<invite_code>/predict", methods=["POST"])
@login_required
def submit_predictions(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    user_id = session["user_id"]
    saved = 0
    blocked = 0

    for key, value in request.form.items():
        if not key.startswith("match_"):
            continue
        match_id = int(key.replace("match_", ""))
        try:
            home_str, away_str = value.split("-")
            home_score = int(home_str)
            away_score = int(away_str)
        except (ValueError, AttributeError):
            continue

        if home_score < 0 or away_score < 0 or home_score > 20 or away_score > 20:
            continue

        with db.db() as conn:
            match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()

        if not match:
            continue

        if not is_prediction_open(match["match_date"], match["match_time"]):
            blocked += 1
            continue

        db.upsert_prediction(user_id, match_id, home_score, away_score)
        saved += 1

    bold_updated = 0
    bold_blocked = 0
    for key, value in request.form.items():
        if not key.startswith("bold_match"):
            continue
        match_id_str = value.strip()
        if not match_id_str:
            continue
        try:
            match_id = int(match_id_str)
        except ValueError:
            continue
        with db.db() as conn:
            match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not match:
            continue
        if not is_prediction_open(match["match_date"], match["match_time"]):
            bold_blocked += 1
            continue
        err = db.set_bold_pick(user_id, match_id)
        if err:
            flash(err, "error")
        else:
            bold_updated += 1
    if bold_updated:
        flash("Bold pick updated — 2× points if you're right!", "success")
    if bold_blocked:
        flash(f"{bold_blocked} bold pick(s) were past the deadline and were not changed.", "error")

    if saved:
        flash(f"Saved {saved} prediction(s).", "success")
    if blocked:
        flash(f"{blocked} prediction(s) were past the deadline (24 hours before kickoff).", "error")
    if not saved and not blocked:
        flash("No predictions to save.", "error")

    return redirect(url_for("pool_dashboard", invite_code=invite_code) + "#matches")


@app.route("/pool/<invite_code>/me")
@login_required
def my_stats_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))
    return redirect(url_for("player_page", invite_code=invite_code, user_id=session["user_id"]))


@app.route("/pool/<invite_code>/player/<int:user_id>")
@login_required
def player_page(invite_code, user_id):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    member = db.get_user(user_id)
    if not member or member["pool_id"] != pool["id"]:
        flash("Player not found in this pool.", "error")
        return redirect(url_for("pool_dashboard", invite_code=invite_code))

    leaderboard = db.get_leaderboard(pool["id"])
    stats = build_player_season_stats(user_id, pool["id"], leaderboard)
    picks_summary = build_player_picks_summary(user_id, pool["id"], session["user_id"])
    members = db.get_pool_members(pool["id"])
    vs_id = request.args.get("vs", type=int)
    h2h = build_head_to_head(user_id, vs_id, pool["id"]) if vs_id and vs_id != user_id else None

    return render_template(
        "player.html",
        pool=pool,
        player=member,
        stats=stats,
        picks_summary=picks_summary,
        members=members,
        h2h=h2h,
        vs_id=vs_id,
        is_you=user_id == session["user_id"],
    )


@app.route("/pool/<invite_code>/guide")
@login_required
def guide_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    deadline = tournament_vote_deadline()
    return render_template(
        "guide.html",
        pool=pool,
        invite_url=invite_url_for(invite_code),
        tournament_deadline=deadline,
        tournament_winner_pts=TOURNAMENT_WINNER_PTS,
        tournament_second_pts=TOURNAMENT_SECOND_PTS,
        tournament_third_pts=TOURNAMENT_THIRD_PTS,
        tournament_scorer_pts=TOURNAMENT_TOP_SCORER_PTS,
    )


@app.route("/pool/<invite_code>/recaps")
@login_required
def recaps_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    return render_template(
        "recaps.html",
        pool=pool,
        recaps=list_matchday_recaps(pool["id"]),
    )


@app.route("/pool/<invite_code>/bold-pick", methods=["POST"])
@login_required
def set_bold_pick_route(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    match_id = request.form.get("match_id", type=int)
    if not match_id:
        flash("Invalid match.", "error")
        return redirect(url_for("pool_dashboard", invite_code=invite_code))

    with db.db() as conn:
        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if not match:
        flash("Match not found.", "error")
        return redirect(url_for("pool_dashboard", invite_code=invite_code))
    if not is_prediction_open(match["match_date"], match["match_time"]):
        flash("Bold picks are locked — the prediction deadline has passed.", "error")
        return redirect(request.referrer or url_for("pool_dashboard", invite_code=invite_code))

    err = db.set_bold_pick(session["user_id"], match_id)
    if err:
        flash(err, "error")
    else:
        flash("Bold pick set — 2× points if correct!", "success")
    return redirect(request.referrer or url_for("pool_dashboard", invite_code=invite_code))


@app.route("/pool/<invite_code>/leaderboard")
@login_required
def leaderboard_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    leaderboard = db.get_leaderboard(pool["id"])
    matches = db.get_all_matches()
    finished = sum(1 for m in matches if m["actual_home"] is not None)

    return render_template(
        "leaderboard.html",
        pool=pool,
        leaderboard=leaderboard,
        leader_message=db.get_leader_message(leaderboard),
        phase_bonus=db.get_pool_phase_bonus_status(pool["id"]),
        phase_bonus_pts=PHASE_BONUS_PTS,
        finished_matches=finished,
        total_matches=len(matches),
    )


def _simulation_overview(matches: list[dict], members: list[dict]) -> list[dict]:
    overview = []
    for member in members:
        preds = db.get_user_predictions(member["id"])
        if not preds:
            continue
        sim = build_predicted_tournament_view(
            matches, preds, member["display_name"], member["id"]
        )
        overview.append(
            {
                "user_id": member["id"],
                "display_name": member["display_name"],
                "prediction_count": member["prediction_count"],
                "predicted_champion": sim["bracket"].get("champion"),
                "group_stage_complete": sim["group_stage_complete"],
            }
        )
    return overview


@app.route("/pool/<invite_code>/standings")
@login_required
def standings_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    matches = enrich_matches(db.get_all_matches())
    view = build_tournament_view(matches)
    view["mode"] = "actual"
    members = db.get_pool_simulation_members(pool["id"])
    user_id = session["user_id"]
    predicted_view = None
    if any(m["id"] == user_id for m in members):
        user = db.get_user(user_id)
        predicted_view = build_predicted_tournament_view(
            matches, db.get_user_predictions(user_id), user["display_name"], user_id
        )

    return render_template(
        "standings.html",
        pool=pool,
        view=view,
        predicted_view=predicted_view,
        simulation_members=members,
        simulation_overview=_simulation_overview(matches, members),
        current_user_id=user_id,
        flag_codes_json=json.dumps(get_flag_codes_for_js()),
        team_slugs_json=json.dumps({t: team_slug(t) for t in get_all_teams()}),
    )


@app.route("/pool/<invite_code>/standings/feed")
@login_required
def standings_feed(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    matches = enrich_matches(db.get_all_matches())
    members = db.get_pool_simulation_members(pool["id"])
    mode = request.args.get("mode", "actual")
    predictor_id = request.args.get("predictor_id", type=int)

    if mode == "predicted":
        if not predictor_id:
            predictor_id = session.get("user_id")
        user = db.get_user(predictor_id) if predictor_id else None
        if not user or user["pool_id"] != pool["id"]:
            return jsonify({"error": "invalid predictor"}), 400
        preds = db.get_user_predictions(predictor_id)
        view = build_predicted_tournament_view(
            matches, preds, user["display_name"], predictor_id
        )
    else:
        view = build_tournament_view(matches)
        view["mode"] = "actual"

    payload = tournament_view_for_json(view)
    payload["predictors"] = members
    payload["simulation_overview"] = _simulation_overview(matches, members)
    return jsonify(payload)


@app.route("/pool/<invite_code>/comments", methods=["GET", "POST"])
@login_required
def comments_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "edit":
            try:
                comment_id = int(request.form.get("comment_id", 0))
            except ValueError:
                flash("Invalid comment.", "error")
            else:
                result = db.update_comment(comment_id, session["user_id"], request.form.get("body", ""))
                if isinstance(result, str):
                    flash(result, "error")
                else:
                    flash("Comment updated.", "success")
        elif action == "delete":
            try:
                comment_id = int(request.form.get("comment_id", 0))
            except ValueError:
                flash("Invalid comment.", "error")
            else:
                error = db.delete_comment(comment_id, session["user_id"])
                if error:
                    flash(error, "error")
                else:
                    flash("Comment deleted.", "success")
        else:
            match_id = request.form.get("match_id", type=int)
            result = db.add_comment(
                pool["id"],
                session["user_id"],
                request.form.get("body", ""),
                match_id=match_id,
            )
            if isinstance(result, str):
                flash(result, "error")
            else:
                mark_comments_seen(pool["id"])
                flash("Comment posted.", "success")
            if match_id:
                return redirect(url_for("match_detail", invite_code=invite_code, match_id=match_id))
        return redirect(url_for("comments_page", invite_code=invite_code))

    mark_comments_seen(pool["id"])
    filter_match = request.args.get("match_id", type=int)
    return render_template(
        "comments.html",
        pool=pool,
        comments=db.get_pool_comments(pool["id"], filter_match),
        filter_match_id=filter_match,
        matches=db.get_all_matches(),
    )


@app.route("/pool/<invite_code>/comments/feed")
@login_required
def comments_feed(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    if request.args.get("mark_seen") == "1":
        mark_comments_seen(pool["id"])

    seen_at = get_comments_seen(pool["id"])
    unread = db.count_unread_comments(pool["id"], seen_at, session["user_id"])
    comments = db.get_pool_comments(pool["id"])

    return jsonify({
        "unread": unread,
        "total": len(comments),
        "comments": [
            {
                "id": c["id"],
                "display_name": c["display_name"],
                "body": c["body"],
                "created_at": c["created_at"],
                "updated_at": c.get("updated_at"),
                "is_you": c["user_id"] == session.get("user_id"),
            }
            for c in comments
        ],
    })


@app.route("/pool/<invite_code>/news/feed")
@login_required
def wc_news_feed(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403
    return jsonify(news_for_json(get_wc_news()))


@app.route("/pool/<invite_code>/tournament-vote/feed")
@login_required
def tournament_vote_feed(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    status = get_tournament_vote_status(session["user_id"])
    return jsonify(status)


@app.route("/pool/<invite_code>/team/<team_slug_name>/stats")
@login_required
def team_stats_feed(invite_code, team_slug_name):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    team_name = team_from_slug(team_slug_name)
    if not team_name:
        return jsonify({"error": "not_found"}), 404

    return jsonify(get_team_live_tournament_stats(team_name))


@app.route("/pool/<invite_code>/matches/live")
@login_required
def matches_live_feed(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    live_score_sync.sync_live_scores()
    matches = enrich_matches(db.get_all_matches())
    live = [m for m in matches if m["is_live"]]
    spotlight = build_pool_spotlight(pool["id"], matches)
    commentary = build_live_commentary(matches)
    return jsonify({
        "live_count": len(live),
        "commentary": commentary_for_json(commentary),
        "spotlight": spotlight_for_json(spotlight, session.get("user_id")),
        "matches": [
            {
                "id": m["id"],
                "home_team": m["home_team"],
                "away_team": m["away_team"],
                "display_home": m["display_home"],
                "display_away": m["display_away"],
                "minute_label": sanitize_minute_label(m["minute_label"]),
                "kickoff_iso": m["kickoff"].isoformat() if m.get("kickoff") else None,
                "status": m["status"],
                "is_live": m["is_live"],
                "is_finished": m["is_finished"],
                "goals": goals_for_json(m.get("goals", [])),
                "cards": cards_for_json(m.get("cards", [])),
            }
            for m in matches
        ],
    })


@app.route("/pool/<invite_code>/predictions/feed")
@login_required
def predictions_feed(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    recent = filter_ticker_predictions(db.get_ticker_pool_predictions(pool["id"]))
    predictors = filter_ticker_predictors(db.get_pool_predictors(pool["id"]))

    return jsonify({
        "recent": [
            {
                "display_name": r["display_name"],
                "home_team": r["home_team"],
                "away_team": r["away_team"],
                "home_score": r["home_score"],
                "away_score": r["away_score"],
                "submitted_at": r["submitted_at"],
                "is_you": r.get("user_id") == session.get("user_id"),
                "is_ai": is_ai_agent(r["display_name"]),
            }
            for r in recent
        ],
        "predictors": [
            {
                "display_name": p["display_name"],
                "prediction_count": p["prediction_count"],
                "last_submitted": p["last_submitted"],
            }
            for p in predictors
        ],
    })


@app.route("/pool/<invite_code>/tournament", methods=["GET", "POST"])
@login_required
def tournament_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    vote_open = is_tournament_vote_open()
    deadline = tournament_vote_deadline()
    user_vote = db.get_tournament_vote(session["user_id"])
    teams = get_all_teams()

    if request.method == "POST":
        if not vote_open:
            flash("Tournament picks are locked — deadline was 1 minute before kickoff.", "error")
            return redirect(url_for("tournament_page", invite_code=invite_code))

        top_scorer = resolve_scorer_pick_value(
            request.form.get("top_scorer", ""),
            request.form.get("top_scorer_custom"),
        )
        result = db.upsert_tournament_vote(
            session["user_id"],
            top_scorer,
            request.form.get("winner", ""),
            request.form.get("second_place", ""),
            request.form.get("third_place", ""),
        )
        if isinstance(result, str):
            flash(result, "error")
        else:
            if user_vote:
                flash("Tournament picks updated.", "success")
            else:
                flash("Tournament picks saved!", "success")
            return redirect(url_for("tournament_page", invite_code=invite_code))

    db.sync_ai_tournament_vote(pool["id"])
    raw_pool_votes = db.get_pool_tournament_votes(pool["id"])
    pool_votes = filter_tournament_votes_for_display(raw_pool_votes, session["user_id"])
    submitted_count = sum(1 for v in raw_pool_votes if v["top_scorer"])
    results = db.get_tournament_results()
    user_points = None
    if user_vote and results:
        user_points = calculate_tournament_points(dict(user_vote), results)

    scorer_board = db.get_tournament_scorer_leaderboard()
    user_scorer_pick = None
    if user_vote:
        user_scorer_pick = get_scorer_status(user_vote["top_scorer"], scorer_board)

    extra_scorer_names = [user_vote["top_scorer"]] if user_vote and user_vote["top_scorer"] else []
    scorer_squads = get_scorer_squads_data(extra_scorer_names)

    return render_template(
        "tournament.html",
        pool=pool,
        teams=teams,
        vote_open=vote_open,
        deadline=deadline,
        user_vote=dict(user_vote) if user_vote else None,
        pool_votes=pool_votes,
        submitted_count=submitted_count,
        results=results,
        user_points=user_points,
        ai_display_name=AI_DISPLAY_NAME,
        scorer_board=scorer_board[:5],
        user_scorer_pick=user_scorer_pick,
        scorer_squads=scorer_squads,
        tournament_picks_revealed=tournament_picks_revealed(),
    )


@app.route("/pool/<invite_code>/team/<team_slug_name>")
@login_required
def team_page(invite_code, team_slug_name):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    team_name = team_from_slug(team_slug_name)
    if not team_name:
        flash("Team not found.", "error")
        return redirect(url_for("pool_dashboard", invite_code=invite_code))

    profile = get_team_profile(team_name)
    matches = [m for m in db.get_all_matches() if m["home_team"] == team_name or m["away_team"] == team_name]

    group_preview = get_group_preview(team_name)
    opponents = group_preview["opponents"] if group_preview else []
    history = get_team_history_bundle(team_name, opponents)
    coach_name = profile.get("coach_info", {}).get("name", profile.get("coach", ""))
    coach_wc_record = get_coach_wc_record(coach_name)

    pool_id = pool["id"]
    pool_predictions = get_team_pool_prediction_stats(pool_id, team_name)
    live_stats = get_team_live_tournament_stats(team_name)
    prediction_accuracy = get_team_prediction_accuracy(pool_id, team_name)

    return render_template(
        "team.html",
        pool=pool,
        profile=profile,
        team_matches=matches,
        group_preview=group_preview,
        history=history,
        coach_wc_record=coach_wc_record,
        pool_predictions=pool_predictions,
        live_stats=live_stats,
        prediction_accuracy=prediction_accuracy,
    )


@app.route("/pool/<invite_code>/scorers")
@login_required
def scorers_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    board = db.get_tournament_scorer_leaderboard()
    events = db.get_tournament_scorer_events()
    user_vote = db.get_tournament_vote(session["user_id"])
    user_pick = None
    if user_vote:
        user_pick = get_scorer_status(user_vote["top_scorer"], board)

    return render_template(
        "scorers.html",
        pool=pool,
        leaderboard=board,
        events=events,
        user_pick=user_pick,
        user_vote=dict(user_vote) if user_vote else None,
    )


@app.route("/pool/<invite_code>/scorers/feed")
@login_required
def scorers_feed(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    live_score_sync.sync_live_scores()
    board = db.get_tournament_scorer_leaderboard()
    events = db.get_tournament_scorer_events()
    user_vote = db.get_tournament_vote(session["user_id"])
    user_pick = None
    if user_vote:
        user_pick = get_scorer_status(user_vote["top_scorer"], board)

    return jsonify({
        "leaderboard": board,
        "events": events,
        "user_pick": user_pick,
        "user_vote": dict(user_vote) if user_vote else None,
    })


@app.route("/pool/<invite_code>/cards")
@login_required
def cards_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("index"))

    data = db.get_player_cards_table()
    matches = db.get_all_matches()

    return render_template(
        "cards.html",
        pool=pool,
        card_summary=data["summary"],
        card_events=data["events"],
        matches=matches,
    )


@app.route("/pool/<invite_code>/cards/feed")
@login_required
def cards_feed(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    live_score_sync.sync_live_scores()
    data = db.get_player_cards_table()
    return jsonify(data)


@app.route("/pool/<invite_code>/match/<int:match_id>")
@login_required
def match_detail(invite_code, match_id):
    pool = db.get_pool_by_code(invite_code)
    if not pool:
        flash("Invalid pool.", "error")
        return redirect(url_for("index"))
    if pool["id"] != session.get("pool_id"):
        flash("You are not in this pool.", "error")
        return redirect(url_for("pool_join", invite_code=invite_code))

    with db.db() as conn:
        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if not match:
        flash("Match not found.", "error")
        return redirect(url_for("pool_dashboard", invite_code=invite_code))

    user_id = session["user_id"]
    enriched = enrich_matches([match], db.get_user_predictions(user_id))[0]
    raw_preds = db.get_pool_predictions_summary(pool["id"], match_id)
    all_preds = filter_predictions_for_display(raw_preds, user_id, dict(match))
    consensus = build_match_consensus(pool["id"], match_id)
    context = get_match_context(match["home_team"], match["away_team"])
    goals = db.get_match_goals(match_id)
    match_comments = db.get_pool_comments(pool["id"], match_id)
    picks_open = not picks_revealed(dict(match))
    leaderboard = db.get_leaderboard(pool["id"])

    return render_template(
        "match.html",
        pool=pool,
        match=enriched,
        goals=goals,
        all_predictions=all_preds,
        match_context=context,
        consensus=consensus,
        match_comments=match_comments,
        picks_revealed=not picks_open,
        can_bold=bool(enriched.get("prediction")) and enriched.get("open"),
        is_bold_pick=bool((enriched.get("prediction") or {}).get("is_bold")),
        leaderboard=leaderboard[:8],
        ai_display_name=AI_DISPLAY_NAME,
    )


@app.route("/pool/<invite_code>/match/<int:match_id>/feed")
@login_required
def match_watch_feed(invite_code, match_id):
    pool = db.get_pool_by_code(invite_code)
    if not pool or pool["id"] != session.get("pool_id"):
        return jsonify({"error": "unauthorized"}), 403

    with db.db() as conn:
        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if not match:
        return jsonify({"error": "not_found"}), 404

    live_score_sync.sync_live_scores()
    enriched = enrich_matches([match])[0]
    raw_preds = db.get_pool_predictions_summary(pool["id"], match_id)
    preds = filter_predictions_for_display(raw_preds, session["user_id"], dict(match))
    return jsonify({
        "match": {
            "id": enriched["id"],
            "display_home": enriched["display_home"],
            "display_away": enriched["display_away"],
            "minute_label": sanitize_minute_label(enriched["minute_label"]),
            "kickoff_iso": enriched["kickoff"].isoformat() if enriched.get("kickoff") else None,
            "is_live": enriched["is_live"],
            "is_finished": enriched["is_finished"],
            "status": enriched["status"],
        },
        "goals": goals_for_json(enriched.get("goals", [])),
        "cards": cards_for_json(enriched.get("cards", [])),
        "consensus": build_match_consensus(pool["id"], match_id),
        "predictions": preds,
        "picks_revealed": picks_revealed(dict(match)),
        "comments": db.get_pool_comments(pool["id"], match_id)[:20],
    })


@app.route("/pool/<invite_code>/admin", methods=["GET", "POST"])
def admin_page(invite_code):
    pool = db.get_pool_by_code(invite_code)
    if not pool:
        flash("Invalid pool.", "error")
        return redirect(url_for("index"))

    session["pool_id"] = pool["id"]
    session["invite_code"] = invite_code

    if request.method == "POST":
        action = request.form.get("action")
        if action == "login":
            if request.form.get("admin_secret") == pool["admin_secret"]:
                session["admin_secret"] = pool["admin_secret"]
                flash("Admin access granted.", "success")
            else:
                flash("Wrong admin password.", "error")
        elif action == "result" and session.get("admin_secret") == pool["admin_secret"]:
            match_id = int(request.form.get("match_id", 0))
            try:
                actual_home = int(request.form.get("actual_home", ""))
                actual_away = int(request.form.get("actual_away", ""))
            except ValueError:
                flash("Invalid score.", "error")
            else:
                db.update_match_result(match_id, actual_home, actual_away)
                db.sync_knockout_stage()
                flash("Result saved — points updated for all players.", "success")
        elif action == "add_match" and session.get("admin_secret") == pool["admin_secret"]:
            home = request.form.get("home_team", "").strip()
            away = request.form.get("away_team", "").strip()
            date = request.form.get("match_date", "").strip()
            time = request.form.get("match_time", "").strip()
            venue = request.form.get("venue", "").strip()
            stage = request.form.get("stage", "round_of_32").strip()
            if home and away and date and time:
                db.add_knockout_match(home, away, date, time, venue, stage)
                flash(f"Added knockout match: {home} vs {away}", "success")
            else:
                flash("Fill in all match fields.", "error")
        elif action == "add_goal" and session.get("admin_secret") == pool["admin_secret"]:
            match_id = int(request.form.get("match_id", 0))
            try:
                minute = int(request.form.get("minute", ""))
                injury = request.form.get("injury_minute", "").strip()
                injury_minute = int(injury) if injury else None
            except ValueError:
                flash("Invalid minute.", "error")
            else:
                result = db.add_match_goal(
                    match_id,
                    request.form.get("team_side", ""),
                    request.form.get("scorer_name", ""),
                    minute,
                    injury_minute,
                    is_penalty=request.form.get("is_penalty") == "1",
                )
                if isinstance(result, str):
                    flash(result, "error")
                else:
                    flash(f"Goal added: {result['scorer_name']}", "success")
        elif action == "add_card" and session.get("admin_secret") == pool["admin_secret"]:
            match_id = int(request.form.get("match_id", 0))
            minute_str = request.form.get("minute", "").strip()
            try:
                minute = int(minute_str) if minute_str else None
            except ValueError:
                flash("Invalid minute.", "error")
            else:
                result = db.add_player_card(
                    match_id,
                    request.form.get("player_name", ""),
                    request.form.get("team", ""),
                    request.form.get("card_type", ""),
                    minute,
                )
                if isinstance(result, str):
                    flash(result, "error")
                else:
                    flash("Card recorded.", "success")
        elif action == "delete_card" and session.get("admin_secret") == pool["admin_secret"]:
            card_id = int(request.form.get("card_id", 0))
            error = db.delete_player_card(card_id)
            if error:
                flash(error, "error")
            else:
                flash("Card removed.", "success")
        elif action == "delete_goal" and session.get("admin_secret") == pool["admin_secret"]:
            goal_id = int(request.form.get("goal_id", 0))
            error = db.delete_match_goal(goal_id)
            if error:
                flash(error, "error")
            else:
                flash("Goal removed.", "success")
        elif action == "add_penalty" and session.get("admin_secret") == pool["admin_secret"]:
            match_id = int(request.form.get("match_id", 0))
            try:
                minute = int(request.form.get("minute", ""))
                injury = request.form.get("injury_minute", "").strip()
                injury_minute = int(injury) if injury else None
            except ValueError:
                flash("Invalid minute.", "error")
            else:
                result = db.add_match_penalty(
                    match_id,
                    request.form.get("taker_team", ""),
                    request.form.get("outcome", ""),
                    minute,
                    request.form.get("taker_name"),
                    request.form.get("goalkeeper_name"),
                    injury_minute,
                )
                if isinstance(result, str):
                    flash(result, "error")
                else:
                    flash("Penalty event recorded.", "success")
        elif action == "delete_penalty" and session.get("admin_secret") == pool["admin_secret"]:
            penalty_id = int(request.form.get("penalty_id", 0))
            error = db.delete_match_penalty(penalty_id)
            if error:
                flash(error, "error")
            else:
                flash("Penalty event removed.", "success")
        elif action == "live" and session.get("admin_secret") == pool["admin_secret"]:
            match_id = int(request.form.get("match_id", 0))
            try:
                live_home = int(request.form.get("live_home", ""))
                live_away = int(request.form.get("live_away", ""))
                live_minute_raw = request.form.get("live_minute", "").strip()
                live_minute = int(live_minute_raw) if live_minute_raw else None
                if live_minute is not None and live_minute <= 0:
                    live_minute = None
            except ValueError:
                flash("Invalid live score.", "error")
            else:
                status = request.form.get("status", "live")
                db.update_match_live(match_id, live_home, live_away, live_minute, status)
                flash("Live score updated.", "success")
        elif action == "tournament_results" and session.get("admin_secret") == pool["admin_secret"]:
            top_scorer = resolve_scorer_pick_value(
                request.form.get("top_scorer", ""),
                request.form.get("top_scorer_custom"),
            )
            winner = request.form.get("winner", "").strip()
            second = request.form.get("second_place", "").strip()
            third = request.form.get("third_place", "").strip()
            allowed = set(get_all_teams())
            if not all([top_scorer, winner, second, third]):
                flash("All tournament result fields are required.", "error")
            elif not {winner, second, third}.issubset(allowed):
                flash("Please select valid teams.", "error")
            elif len({winner, second, third}) < 3:
                flash("Winner, 2nd, and 3rd must be different teams.", "error")
            else:
                db.save_tournament_results(top_scorer, winner, second, third)
                flash("Tournament results saved — leaderboard bonus points updated.", "success")
        elif action == "delete_user" and session.get("admin_secret") == pool["admin_secret"]:
            try:
                user_id = int(request.form.get("user_id", 0))
            except ValueError:
                flash("Invalid user.", "error")
            else:
                error = db.delete_user(user_id, pool["id"])
                if error:
                    flash(error, "error")
                else:
                    if session.get("user_id") == user_id:
                        session.pop("user_id", None)
                        session.pop("display_name", None)
                    flash("User deleted — their predictions, comments, and tournament picks were removed.", "success")
        elif action == "rename_user" and session.get("admin_secret") == pool["admin_secret"]:
            try:
                user_id = int(request.form.get("user_id", 0))
            except ValueError:
                flash("Invalid user.", "error")
            else:
                result = db.rename_user(user_id, pool["id"], request.form.get("new_display_name", ""))
                if isinstance(result, str):
                    flash(result, "error")
                else:
                    if session.get("user_id") == user_id:
                        session["display_name"] = result["display_name"]
                    flash(
                        f'Renamed "{result["old_display_name"]}" → "{result["display_name"]}". '
                        "They can return with the same invite link and their new name.",
                        "success",
                    )
        elif action == "delete_comment" and session.get("admin_secret") == pool["admin_secret"]:
            try:
                comment_id = int(request.form.get("comment_id", 0))
            except ValueError:
                flash("Invalid comment.", "error")
            else:
                error = db.admin_delete_comment(comment_id, pool["id"])
                if error:
                    flash(error, "error")
                else:
                    flash("Comment deleted.", "success")
        elif action == "delete_user_comments" and session.get("admin_secret") == pool["admin_secret"]:
            try:
                user_id = int(request.form.get("user_id", 0))
            except ValueError:
                flash("Invalid user.", "error")
            else:
                error = db.admin_delete_user_comments(user_id, pool["id"])
                if error:
                    flash(error, "error")
                else:
                    flash("All comments for that member were deleted.", "success")
        elif action == "admin_predictions" and session.get("admin_secret") == pool["admin_secret"]:
            try:
                user_id = int(request.form.get("user_id", 0))
            except ValueError:
                flash("Invalid user.", "error")
            else:
                user = db.get_user(user_id)
                if not user or user["pool_id"] != pool["id"]:
                    flash("User not found in this pool.", "error")
                elif is_ai_agent(user["display_name"]):
                    flash("Use the AI sync tools for AI members — not manual override.", "error")
                else:
                    saved = 0
                    for key in request.form:
                        if not key.startswith("pred_") or not key.endswith("_home"):
                            continue
                        try:
                            match_id = int(key.split("_")[1])
                        except (ValueError, IndexError):
                            continue
                        home_str = request.form.get(f"pred_{match_id}_home", "").strip()
                        away_str = request.form.get(f"pred_{match_id}_away", "").strip()
                        if not home_str or not away_str:
                            continue
                        try:
                            home_score = int(home_str)
                            away_score = int(away_str)
                        except ValueError:
                            continue
                        if home_score < 0 or away_score < 0 or home_score > 20 or away_score > 20:
                            continue
                        db.upsert_prediction(user_id, match_id, home_score, away_score)
                        saved += 1
                    bold_match = request.form.get("bold_match_id", "").strip()
                    if bold_match:
                        try:
                            err = db.set_bold_pick(user_id, int(bold_match))
                            if err:
                                flash(err, "error")
                            else:
                                flash("Bold pick updated for member.", "success")
                        except ValueError:
                            pass
                    if saved:
                        flash(f"Saved {saved} match prediction(s) for {user['display_name']} (deadline bypassed).", "success")
                    elif not bold_match:
                        flash("No predictions to save.", "error")
        elif action == "admin_tournament_vote" and session.get("admin_secret") == pool["admin_secret"]:
            try:
                user_id = int(request.form.get("user_id", 0))
            except ValueError:
                flash("Invalid user.", "error")
            else:
                user = db.get_user(user_id)
                if not user or user["pool_id"] != pool["id"]:
                    flash("User not found in this pool.", "error")
                elif is_ai_agent(user["display_name"]):
                    flash("Use the AI sync tools for AI members — not manual override.", "error")
                else:
                    top_scorer = resolve_scorer_pick_value(
                        request.form.get("top_scorer", ""),
                        request.form.get("top_scorer_custom"),
                    )
                    result = db.upsert_tournament_vote(
                        user_id,
                        top_scorer,
                        request.form.get("winner", ""),
                        request.form.get("second_place", ""),
                        request.form.get("third_place", ""),
                    )
                    if isinstance(result, str):
                        flash(result, "error")
                    else:
                        flash(
                            f"Tournament picks saved for {user['display_name']} (deadline bypassed).",
                            "success",
                        )

    is_admin = session.get("admin_secret") == pool["admin_secret"]
    matches = enrich_matches(db.get_all_matches())

    cards_data = db.get_player_cards_table()
    tournament_results = db.get_tournament_results()
    extra_scorer_names = [tournament_results["top_scorer"]] if tournament_results and tournament_results.get("top_scorer") else []
    scorer_squads = get_scorer_squads_data(extra_scorer_names)

    members = db.get_pool_members_with_stats(pool["id"]) if is_admin else []
    pool_comments = db.get_pool_comments(pool["id"])[:50] if is_admin else []
    edit_user_id = request.args.get("user_id", type=int) if is_admin else None
    if is_admin and not edit_user_id and request.method == "POST":
        if request.form.get("action") in ("admin_predictions", "admin_tournament_vote", "rename_user"):
            edit_user_id = request.form.get("user_id", type=int)
    edit_user = None
    edit_user_matches = []
    edit_user_vote = None
    if edit_user_id:
        edit_user = db.get_user(edit_user_id)
        if not edit_user or edit_user["pool_id"] != pool["id"]:
            edit_user_id = None
            edit_user = None
        else:
            user_preds = db.get_user_predictions(edit_user_id)
            edit_user_matches = enrich_matches(db.get_all_matches(), user_preds)
            edit_user_vote = db.get_tournament_vote(edit_user_id)

    return render_template(
        "admin.html",
        pool=pool,
        matches=matches,
        is_admin=is_admin,
        invite_url=invite_url_for(invite_code),
        teams=get_all_teams(),
        tournament_results=tournament_results,
        scorer_board=db.get_tournament_scorer_leaderboard(),
        card_events=cards_data["events"],
        scorer_squads=scorer_squads,
        members=members,
        pool_comments=pool_comments,
        edit_user_id=edit_user_id,
        edit_user=edit_user,
        edit_user_matches=edit_user_matches,
        edit_user_vote=edit_user_vote,
        live_sync=live_score_sync.get_sync_status(),
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
