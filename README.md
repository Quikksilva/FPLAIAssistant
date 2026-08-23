# FPL AI Assistant

Personal Fantasy Premier League data pipeline + weekly review automation.

- `fpl_data_pull.py` - stdlib-only Python script that hits the official FPL
  API (fantasy.premierleague.com) directly. No scraping, no pip installs.
  Writes fresh CSVs to `fpl_data/` each run:
  - `players.csv`, `teams.csv`, `fixtures.csv` - full league data
  - `price_changes.csv` - price movers since the previous run
  - `manager_summary.csv`, `squad_current.csv` - your actual squad, bank,
    free transfers, chips, and rank, pulled automatically via your FPL
    Team ID (public API, no login needed)
  - `gw_status.json` - whether the current Gameweek has finished and had
    its points locked in, so automation can detect "GW just completed"
    without assuming a fixed day/time

- A scheduled cloud routine runs this daily, checks `gw_status.json`, and
  produces a full structured weekly review once each Gameweek's points
  have locked in.

Run manually any time with:

```bash
python fpl_data_pull.py
```
