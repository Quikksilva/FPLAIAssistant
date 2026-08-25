#!/usr/bin/env python3
"""
FPL AI Season - data pull script
=================================

Fetches accurate, complete data straight from the OFFICIAL Fantasy Premier
League API (fantasy.premierleague.com) and writes it to plain CSV/JSON files
in ./fpl_data/:

  players.csv          one row per player: price, form, points, injury/news
                        status, set-piece duties, underlying stats
                        (xG/xA/DEFCON etc.)
  teams.csv             one row per club: strength ratings + a simple
                        "recent form" computed from results over their last
                        5 played fixtures
  fixtures.csv          every fixture this season with FPL's Fixture
                        Difficulty Rating (FDR)
  price_changes.csv     ONLY written if a previous players.csv is found -
                        shows who rose/fell in price since the last pull
  manager_summary.csv   your team value, bank, overall rank, and a computed
                        free-transfers-available figure (only written if a
                        team ID is configured - see below)
  squad_current.csv     your actual 15-man squad for the most recent
                        Gameweek picks are available for (player, position,
                        starting/bench, captain/vice, purchase price) - only
                        written if a team ID is configured
  gw_status.json        small state file: which Gameweek is "current", and
                        whether it has finished + had its data confirmed
                        (i.e. points locked). Used to detect "GW just
                        finished" without guessing a fixed day/time.

TEAM ID: set the FPL_TEAM_ID environment variable, or pass it as the first
command-line argument, to also pull your actual squad/bank/transfers/chips
from the public (no-login-needed) FPL API. Find your team ID in the URL
when viewing your team on the FPL website:
  fantasy.premierleague.com/entry/<TEAM_ID>/event/<GW>

Run it manually whenever you want fresh data (e.g. once a Gameweek, before
asking Claude for your weekly review), or let the scheduled cloud routine
run it automatically.

Requirements: Python 3.7+ only. No pip installs needed (uses only the
standard library), so it should run as-is on Windows/Mac/Linux.

Usage:
    python3 fpl_data_pull.py
    python3 fpl_data_pull.py 5919706        # explicit team ID
    FPL_TEAM_ID=5919706 python3 fpl_data_pull.py
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BASE = "https://fantasy.premierleague.com/api"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fpl_data")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; fpl-data-pull/1.0; "
        "+https://fantasy.premierleague.com)"
    ),
    "Accept": "application/json",
}

DEFAULT_TEAM_ID = "5919706"


def fetch_json(path):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"ERROR fetching {url}: {e}", file=sys.stderr)
        return None


def money(tenths):
    """FPL prices are stored in tenths of a million, e.g. 105 -> 10.5"""
    if tenths is None:
        return ""
    return round(tenths / 10.0, 1)


def pct(x):
    return "" if x in (None, "") else x


def find_current_event(events):
    current = next((e for e in events if e.get("is_current")), None)
    if current:
        return current
    finished = [e for e in events if e.get("finished")]
    if finished:
        return finished[-1]
    nxt = next((e for e in events if e.get("is_next")), None)
    return nxt or (events[0] if events else None)


def build_team_lookup(teams):
    return {t["id"]: t for t in teams}


def build_position_lookup(element_types):
    return {et["id"]: et["singular_name_short"] for et in element_types}


PLAYER_FIELDS = [
    "id", "web_name", "full_name", "team_short", "team_name", "position",
    "price", "price_change_this_gw", "price_change_season",
    "status", "chance_playing_this_round", "chance_playing_next_round",
    "news", "news_added",
    "total_points", "event_points", "points_per_game", "form", "ep_next", "ep_this",
    "minutes", "starts",
    "goals_scored", "assists", "clean_sheets", "goals_conceded",
    "own_goals", "penalties_saved", "penalties_missed",
    "yellow_cards", "red_cards", "saves", "bonus", "bps",
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_conceded",
    "clearances_blocks_interceptions", "recoveries", "tackles",
    "defensive_contribution", "defensive_contribution_per_90",
    "influence", "creativity", "threat", "ict_index",
    "selected_by_percent", "transfers_in_event", "transfers_out_event",
    "value_season",
    "corners_and_indirect_freekicks_order", "direct_freekicks_order",
    "penalties_order",
    "dreamteam_count",
]


def build_player_rows(elements, team_lookup, pos_lookup):
    rows = []
    for p in elements:
        team = team_lookup.get(p.get("team"), {})
        row = {
            "id": p.get("id"),
            "web_name": p.get("web_name"),
            "full_name": f"{p.get('first_name', '')} {p.get('second_name', '')}".strip(),
            "team_short": team.get("short_name", ""),
            "team_name": team.get("name", ""),
            "position": pos_lookup.get(p.get("element_type"), ""),
            "price": money(p.get("now_cost")),
            "price_change_this_gw": money(p.get("cost_change_event")),
            "price_change_season": money(p.get("cost_change_start")),
            "status": p.get("status"),
            "chance_playing_this_round": pct(p.get("chance_of_playing_this_round")),
            "chance_playing_next_round": pct(p.get("chance_of_playing_next_round")),
            "news": p.get("news", ""),
            "news_added": p.get("news_added", ""),
            "total_points": p.get("total_points"),
            "event_points": p.get("event_points"),
            "points_per_game": p.get("points_per_game"),
            "form": p.get("form"),
            "ep_next": p.get("ep_next"),
            "ep_this": p.get("ep_this"),
            "minutes": p.get("minutes"),
            "starts": p.get("starts"),
            "goals_scored": p.get("goals_scored"),
            "assists": p.get("assists"),
            "clean_sheets": p.get("clean_sheets"),
            "goals_conceded": p.get("goals_conceded"),
            "own_goals": p.get("own_goals"),
            "penalties_saved": p.get("penalties_saved"),
            "penalties_missed": p.get("penalties_missed"),
            "yellow_cards": p.get("yellow_cards"),
            "red_cards": p.get("red_cards"),
            "saves": p.get("saves"),
            "bonus": p.get("bonus"),
            "bps": p.get("bps"),
            "expected_goals": p.get("expected_goals"),
            "expected_assists": p.get("expected_assists"),
            "expected_goal_involvements": p.get("expected_goal_involvements"),
            "expected_goals_conceded": p.get("expected_goals_conceded"),
            "clearances_blocks_interceptions": p.get("clearances_blocks_interceptions"),
            "recoveries": p.get("recoveries"),
            "tackles": p.get("tackles"),
            "defensive_contribution": p.get("defensive_contribution"),
            "defensive_contribution_per_90": p.get("defensive_contribution_per_90"),
            "influence": p.get("influence"),
            "creativity": p.get("creativity"),
            "threat": p.get("threat"),
            "ict_index": p.get("ict_index"),
            "selected_by_percent": p.get("selected_by_percent"),
            "transfers_in_event": p.get("transfers_in_event"),
            "transfers_out_event": p.get("transfers_out_event"),
            "value_season": p.get("value_season"),
            "corners_and_indirect_freekicks_order": p.get("corners_and_indirect_freekicks_order"),
            "direct_freekicks_order": p.get("direct_freekicks_order"),
            "penalties_order": p.get("penalties_order"),
            "dreamteam_count": p.get("dreamteam_count"),
        }
        rows.append(row)
    return rows


def write_csv(path, fieldnames, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def compute_team_form(teams, fixtures, n=5):
    by_team = {t["id"]: [] for t in teams}
    finished = [f for f in fixtures if f.get("finished")]
    finished.sort(key=lambda f: (f.get("event") or 0, f.get("kickoff_time") or ""))
    for f in finished:
        th, ta = f["team_h"], f["team_a"]
        hs, aws = f.get("team_h_score"), f.get("team_a_score")
        if hs is None or aws is None:
            continue
        by_team[th].append(("H", hs, aws))
        by_team[ta].append(("A", aws, hs))

    form = {}
    for tid, games in by_team.items():
        last = games[-n:]
        w = d = l = gf = ga = cs = 0
        results = []
        for venue, gs, gc in last:
            gf += gs
            ga += gc
            if gc == 0:
                cs += 1
            if gs > gc:
                w += 1
                results.append("W")
            elif gs == gc:
                d += 1
                results.append("D")
            else:
                l += 1
                results.append("L")
        form[tid] = {
            "played_last_n": len(last),
            "form_string": "".join(results),
            "wins": w, "draws": d, "losses": l,
            "goals_for": gf, "goals_against": ga,
            "clean_sheets": cs,
        }
    return form


def build_team_rows(teams, team_form):
    rows = []
    for t in teams:
        tf = team_form.get(t["id"], {})
        rows.append({
            "id": t["id"],
            "name": t["name"],
            "short_name": t["short_name"],
            "strength_overall": t.get("strength"),
            "strength_attack_home": t.get("strength_attack_home"),
            "strength_attack_away": t.get("strength_attack_away"),
            "strength_defence_home": t.get("strength_defence_home"),
            "strength_defence_away": t.get("strength_defence_away"),
            "recent_form": tf.get("form_string", ""),
            "recent_played": tf.get("played_last_n", 0),
            "recent_wins": tf.get("wins", 0),
            "recent_draws": tf.get("draws", 0),
            "recent_losses": tf.get("losses", 0),
            "recent_goals_for": tf.get("goals_for", 0),
            "recent_goals_against": tf.get("goals_against", 0),
            "recent_clean_sheets": tf.get("clean_sheets", 0),
        })
    return rows


def build_fixture_rows(fixtures, team_lookup):
    rows = []
    for f in fixtures:
        th = team_lookup.get(f.get("team_h"), {})
        ta = team_lookup.get(f.get("team_a"), {})
        rows.append({
            "event": f.get("event"),
            "kickoff_time": f.get("kickoff_time"),
            "finished": f.get("finished"),
            "team_h": th.get("short_name", ""),
            "team_a": ta.get("short_name", ""),
            "team_h_score": f.get("team_h_score"),
            "team_a_score": f.get("team_a_score"),
            "team_h_difficulty": f.get("team_h_difficulty"),
            "team_a_difficulty": f.get("team_a_difficulty"),
        })
    return rows


def diff_price_changes(prev_path, new_rows):
    if not os.path.exists(prev_path):
        return None
    prev_by_id = {}
    with open(prev_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            prev_by_id[row.get("id")] = row

    changes = []
    for row in new_rows:
        pid = str(row["id"])
        prev = prev_by_id.get(pid)
        if not prev or "price" not in prev:
            continue
        try:
            old_price = float(prev["price"]) if prev["price"] != "" else None
            new_price = float(row["price"]) if row["price"] != "" else None
        except ValueError:
            continue
        if old_price is not None and new_price is not None and old_price != new_price:
            changes.append({
                "id": row["id"],
                "web_name": row["web_name"],
                "team_short": row["team_short"],
                "old_price": old_price,
                "new_price": new_price,
                "change": round(new_price - old_price, 1),
            })
    changes.sort(key=lambda c: c["change"])
    return changes


# ---------------------------------------------------------------------------
# Manager (your team) data - only runs if a team ID is available
# ---------------------------------------------------------------------------

def resolve_team_id():
    if len(sys.argv) > 1 and sys.argv[1].strip().isdigit():
        return sys.argv[1].strip()
    env_id = os.environ.get("FPL_TEAM_ID", "").strip()
    if env_id.isdigit():
        return env_id
    if DEFAULT_TEAM_ID:
        return DEFAULT_TEAM_ID
    return None


def compute_free_transfers(history_current, chip_events):
    """
    Replay each finished Gameweek's transfer activity to estimate free
    transfers available for the NEXT Gameweek, per 2026/27 rules: 1 FT/GW,
    rolls over to a cap of 5. Transfers made in a Wildcard/Free Hit event
    don't cost points and don't affect the free-transfer count.

    This is a best-effort reconstruction from public data (the API doesn't
    expose "free transfers remaining" directly) - treat it as a strong
    estimate, not gospel, and verify in-app if a decision hinges on it.
    """
    ft = 1
    for gw in sorted(history_current, key=lambda g: g["event"]):
        event = gw["event"]
        if event == 1:
            continue  # GW1 is initial squad selection, no FT concept yet
        made = gw.get("event_transfers", 0) or 0
        if event in chip_events:
            # Wildcard/Free Hit: transfers don't consume or cost anything
            ft = min(ft + 1, 5)
            continue
        if made <= ft:
            ft = min(ft - made + 1, 5)
        else:
            ft = 1  # took a hit; resets to 1 next GW
    return ft


def pull_manager_data(team_id, current_event_id):
    entry = fetch_json(f"/entry/{team_id}/")
    if entry is None:
        print(f"Could not fetch manager entry {team_id} (private team, or invalid ID?). "
              "Skipping manager_summary.csv / squad_current.csv.", file=sys.stderr)
        return

    history = fetch_json(f"/entry/{team_id}/history/")
    chips = (history or {}).get("chips", [])
    chip_events = {c["event"] for c in chips}
    history_current = (history or {}).get("current", [])

    free_transfers = compute_free_transfers(history_current, chip_events)

    latest_gw = None
    if history_current:
        latest_gw = max(g["event"] for g in history_current)
    picks_event = latest_gw or current_event_id

    picks_data = fetch_json(f"/entry/{team_id}/event/{picks_event}/picks/") if picks_event else None

    # Points scored in picks_event specifically (not season-cumulative) - the
    # picks endpoint's entry_history.points field is exactly this, straight
    # from the API, so no need to sum it ourselves.
    gameweek_points = picks_data["entry_history"]["points"] if picks_data else ""
    points_on_bench = picks_data["entry_history"]["points_on_bench"] if picks_data else ""

    summary_row = {
        "team_id": team_id,
        "manager_name": f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}".strip(),
        "team_name": entry.get("name", ""),
        "overall_rank": entry.get("summary_overall_rank", ""),
        "overall_points": entry.get("summary_overall_points", ""),
        "gameweek_reflected": picks_event,
        "gameweek_points": gameweek_points,
        "points_on_bench": points_on_bench,
        "team_value": money(picks_data["entry_history"]["value"]) if picks_data else "",
        "bank": money(picks_data["entry_history"]["bank"]) if picks_data else "",
        "free_transfers_available_next_gw": free_transfers,
        "chips_used": "; ".join(f"{c['name']} (GW{c['event']})" for c in chips) if chips else "None",
        "active_chip_this_gw": (picks_data.get("active_chip") if picks_data else "") or "None",
        "event_transfers_cost_this_gw": picks_data["entry_history"]["event_transfers_cost"] if picks_data else "",
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    write_csv(
        os.path.join(OUT_DIR, "manager_summary.csv"),
        list(summary_row.keys()),
        [summary_row],
    )
    print(f"Wrote manager_summary.csv for team {team_id} "
          f"(FTs available next GW: {free_transfers}, bank: £{summary_row['bank']}m)")

    if not picks_data:
        return

    bootstrap = fetch_json("/bootstrap-static/")
    elements_by_id = {e["id"]: e for e in bootstrap["elements"]} if bootstrap else {}
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]} if bootstrap else {}
    pos_lookup = build_position_lookup(bootstrap["element_types"]) if bootstrap else {}

    # Per-player points for picks_event specifically, from the gameweek-live
    # endpoint (not bootstrap's event_points field, which reflects whatever
    # event is currently "live" and would go stale/reset once the next GW
    # starts - this endpoint always returns that exact gameweek's stats).
    live_data = fetch_json(f"/event/{picks_event}/live/")
    live_points_by_element = {}
    if live_data:
        for el in live_data.get("elements", []):
            live_points_by_element[el["id"]] = el.get("stats", {}).get("total_points", 0)

    squad_rows = []
    for pick in picks_data.get("picks", []):
        el = elements_by_id.get(pick["element"], {})
        team = teams_by_id.get(el.get("team"), {})
        gw_pts_raw = live_points_by_element.get(pick["element"], 0)
        multiplier = pick.get("multiplier", 1) or 0
        squad_rows.append({
            "web_name": el.get("web_name", ""),
            "team_short": team.get("short_name", ""),
            "position": pos_lookup.get(el.get("element_type"), ""),
            "squad_slot": pick["position"],
            "is_starting": pick["position"] <= 11,
            "is_captain": pick.get("is_captain", False),
            "is_vice_captain": pick.get("is_vice_captain", False),
            "multiplier": multiplier,
            "gw_points_raw": gw_pts_raw,
            "gw_points_scored": gw_pts_raw * multiplier,
            "current_price": money(el.get("now_cost")),
            "purchase_price": money(pick.get("purchase_price")) if "purchase_price" in pick else "",
            "status": el.get("status"),
            "chance_of_playing_next_round": el.get("chance_of_playing_next_round"),
            "news": el.get("news", ""),
        })
    squad_rows.sort(key=lambda r: r["squad_slot"])

    write_csv(
        os.path.join(OUT_DIR, "squad_current.csv"),
        ["web_name", "team_short", "position", "squad_slot", "is_starting",
         "is_captain", "is_vice_captain", "multiplier", "gw_points_raw",
         "gw_points_scored", "current_price", "purchase_price", "status",
         "chance_of_playing_next_round", "news"],
        squad_rows,
    )
    print(f"Wrote squad_current.csv (GW{picks_event} picks, {len(squad_rows)} players, "
          f"{gameweek_points} team points that GW)")


def write_gw_status(events, fixtures):
    """
    Small state file describing gameweek timing so a scheduled job can
    detect 'this Gameweek just finished and points are locked in' without
    assuming a fixed day/time - GW length varies (blanks, doubles,
    rearranged/midweek fixtures, international breaks).
    """
    current = find_current_event(events)
    most_recent_finished = None
    for e in sorted(events, key=lambda e: e["id"]):
        if e.get("finished"):
            most_recent_finished = e

    status = {
        "current_event_id": current.get("id") if current else None,
        "current_event_name": current.get("name") if current else None,
        "current_event_finished": current.get("finished") if current else None,
        "current_event_data_checked": current.get("data_checked") if current else None,
        "most_recently_finished_event_id": most_recent_finished.get("id") if most_recent_finished else None,
        "most_recently_finished_event_data_checked": most_recent_finished.get("data_checked") if most_recent_finished else None,
        "next_event_id": next((e["id"] for e in events if e.get("is_next")), None),
        "next_event_deadline": next((e["deadline_time"] for e in events if e.get("is_next")), None),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(os.path.join(OUT_DIR, "gw_status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    return status


def main():
    print("Fetching official FPL data...")
    bootstrap = fetch_json("/bootstrap-static/")
    fixtures = fetch_json("/fixtures/")
    if bootstrap is None or fixtures is None:
        print("Aborting: could not reach the FPL API.", file=sys.stderr)
        sys.exit(1)

    events = bootstrap.get("events", [])
    teams = bootstrap.get("teams", [])
    elements = bootstrap.get("elements", [])
    element_types = bootstrap.get("element_types", [])

    team_lookup = build_team_lookup(teams)
    pos_lookup = build_position_lookup(element_types)

    current_event = find_current_event(events)
    gw_label = current_event.get("name") if current_event else "Unknown"
    print(f"Most relevant Gameweek: {gw_label}")

    player_rows = build_player_rows(elements, team_lookup, pos_lookup)
    team_form = compute_team_form(teams, fixtures)
    team_rows = build_team_rows(teams, team_form)
    fixture_rows = build_fixture_rows(fixtures, team_lookup)

    players_path = os.path.join(OUT_DIR, "players.csv")
    teams_path = os.path.join(OUT_DIR, "teams.csv")
    fixtures_path = os.path.join(OUT_DIR, "fixtures.csv")
    price_changes_path = os.path.join(OUT_DIR, "price_changes.csv")

    changes = diff_price_changes(players_path, player_rows)

    write_csv(players_path, PLAYER_FIELDS, player_rows)
    write_csv(teams_path, list(team_rows[0].keys()) if team_rows else [], team_rows)
    write_csv(fixtures_path, list(fixture_rows[0].keys()) if fixture_rows else [], fixture_rows)

    if changes:
        write_csv(
            price_changes_path,
            ["id", "web_name", "team_short", "old_price", "new_price", "change"],
            changes,
        )
        print(f"Price changes since last pull: {len(changes)} (see price_changes.csv)")
    elif os.path.exists(price_changes_path):
        os.remove(price_changes_path)

    gw_status = write_gw_status(events, fixtures)
    print(f"GW status: current={gw_status['current_event_id']} "
          f"finished={gw_status['current_event_finished']} "
          f"data_checked={gw_status['current_event_data_checked']}")

    team_id = resolve_team_id()
    if team_id:
        pull_manager_data(team_id, current_event.get("id") if current_event else None)
    else:
        print("No FPL_TEAM_ID set - skipping manager_summary.csv / squad_current.csv. "
              "Pass a team ID as an argument or set FPL_TEAM_ID to enable this.")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\nDone. Pulled at {stamp}.")
    print(f"Players: {len(player_rows)}  Teams: {len(team_rows)}  Fixtures: {len(fixture_rows)}")
    print(f"Files written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
