from pathlib import Path
import numpy as np
import pandas as pd

try:
    from pybaseball import playerid_reverse_lookup
except Exception:
    playerid_reverse_lookup = None


# =========================
# Settings
# =========================

DATE = "2026-04-28"
TEAM = "TOR"

# =========================
# Paths
# =========================

base_dir = Path(__file__).resolve().parents[1]
data_file = base_dir / "data" / f"{DATE}-bluejays-statcast.csv"

reports_dir = base_dir / "reports"
tables_dir = reports_dir / "tables"
tables_dir.mkdir(parents=True, exist_ok=True)

output_report = reports_dir / f"{DATE}-bluejays-advanced-game-report.md"
charts_dir = base_dir / "charts" / DATE

pitch_movement_chart = f"../charts/{DATE}/{DATE}-pitch-movement.png"
ev_la_chart = f"../charts/{DATE}/{DATE}-exit-velocity-launch-angle.png"
spray_chart = f"../charts/{DATE}/{DATE}-spray-chart.png"
# =========================
# Load data
# =========================

df = pd.read_csv(data_file)
def format_name(name):
    if pd.isna(name):
        return "Unknown"

    name = str(name).strip()

    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}"

    return name

df["player_name"] = df["player_name"].apply(format_name)
# =========================
# Basic cleaning
# =========================

for col in ["pitch_type", "stand", "p_throws", "description"]:
    if col in df.columns:
        df[col] = df[col].fillna("Unknown")

numeric_cols = [
    "release_speed", "pfx_x", "pfx_z", "zone",
    "launch_speed", "launch_angle", "launch_speed_angle",
    "hc_x", "hc_y"
]

for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# =========================
# Team role: batting / pitching
# =========================

df["batting_team"] = np.where(
    df["inning_topbot"] == "Top",
    df["away_team"],
    df["home_team"]
)

df["pitching_team"] = np.where(
    df["inning_topbot"] == "Top",
    df["home_team"],
    df["away_team"]
)

tor_pitching = df[df["pitching_team"] == TEAM].copy()
tor_batting = df[df["batting_team"] == TEAM].copy()

# =========================
# Batter names
# =========================

def get_player_name_map(player_ids):
    if playerid_reverse_lookup is None:
        return {}

    ids = (
        pd.Series(player_ids)
        .dropna()
        .astype(int)
        .drop_duplicates()
        .tolist()
    )

    if not ids:
        return {}

    try:
        lookup = playerid_reverse_lookup(ids, key_type="mlbam")

        if "key_mlbam" not in lookup.columns:
            return {}

        lookup["full_name"] = (
            lookup["name_first"].fillna("") + " " + lookup["name_last"].fillna("")
        ).str.strip()

        return dict(zip(lookup["key_mlbam"].astype(int), lookup["full_name"]))

    except Exception as e:
        print(f"Could not look up batter names: {e}")
        return {}


batter_name_map = get_player_name_map(df["batter"])

def format_batter_name(x):
    try:
        player_id = int(x)
        return batter_name_map.get(player_id, f"Batter {player_id}")
    except Exception:
        return "Unknown Batter"


df["batter_name"] = df["batter"].apply(format_batter_name)
tor_batting["batter_name"] = tor_batting["batter"].apply(format_batter_name)
tor_pitching["batter_name"] = tor_pitching["batter"].apply(format_batter_name)

# =========================
# Derived metrics
# =========================

# Movement: Statcast pfx_x / pfx_z are in feet, so convert to inches.
# h_mov_in is flipped to show movement from the pitcher's perspective.
df["h_mov_in"] = -12 * df["pfx_x"]
df["v_mov_in"] = 12 * df["pfx_z"]

tor_pitching["h_mov_in"] = -12 * tor_pitching["pfx_x"]
tor_pitching["v_mov_in"] = 12 * tor_pitching["pfx_z"]

tor_batting["h_mov_in"] = -12 * tor_batting["pfx_x"]
tor_batting["v_mov_in"] = 12 * tor_batting["pfx_z"]

swing_descriptions = [
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "missed_bunt",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
]

whiff_descriptions = [
    "swinging_strike",
    "swinging_strike_blocked",
    "missed_bunt",
]

foul_descriptions = [
    "foul",
    "foul_tip",
    "foul_bunt",
]

bip_descriptions = [
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
]

for data in [df, tor_pitching, tor_batting]:
    data["is_swing"] = data["description"].isin(swing_descriptions)
    data["is_whiff"] = data["description"].isin(whiff_descriptions)
    data["is_foul"] = data["description"].isin(foul_descriptions)
    data["is_bip"] = data["description"].isin(bip_descriptions)
    data["is_take"] = ~data["is_swing"]

    data["is_zone"] = data["zone"].isin([1, 2, 3, 4, 5, 6, 7, 8, 9])
    data["is_out_zone"] = data["zone"].notna() & ~data["is_zone"]
    data["is_chase"] = data["is_out_zone"] & data["is_swing"]

    data["is_bbe"] = data["launch_speed"].notna()
    data["is_hard_hit"] = data["launch_speed"] >= 95
    data["is_barrel"] = data["launch_speed_angle"] == 6
    data["is_sweet_spot"] = data["launch_angle"].between(8, 32)

    data["base_situation"] = np.where(
        data[["on_1b", "on_2b", "on_3b"]].notna().any(axis=1),
        "Runners On",
        "No Runners"
    )


# =========================
# Helper functions
# =========================

def add_rate(table, numerator, denominator, output_col):
    table[output_col] = np.where(
        table[denominator] > 0,
        table[numerator] / table[denominator] * 100,
        0
    )
    table[output_col] = table[output_col].round(1)
    return table


def round_existing(table, cols, digits=1):
    for col in cols:
        if col in table.columns:
            table[col] = table[col].round(digits)
    return table


def md_table(table, columns, max_rows=20):
    if table.empty:
        return ["_No data available._", ""]

    t = table[columns].head(max_rows).copy()

    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("|" + "|".join(["---"] * len(columns)) + "|")

    for _, row in t.iterrows():
        values = []
        for col in columns:
            val = row[col]
            if isinstance(val, float):
                values.append(f"{val:.1f}")
            else:
                values.append(str(val))
        lines.append("| " + " | ".join(values) + " |")

    lines.append("")
    return lines


# =========================
# 1) Pitcher movement by batter side
# =========================

pitcher_movement = (
    tor_pitching
    .groupby(["player_name", "pitch_type", "stand"])
    .agg(
        pitches=("pitch_type", "count"),
        avg_velocity=("release_speed", "mean"),
        avg_h_mov=("h_mov_in", "mean"),
        avg_v_mov=("v_mov_in", "mean"),
        swings=("is_swing", "sum"),
        whiffs=("is_whiff", "sum"),
        fouls=("is_foul", "sum"),
        balls_in_play=("is_bip", "sum"),
        out_zone_pitches=("is_out_zone", "sum"),
        chases=("is_chase", "sum"),
    )
    .reset_index()
)

pitcher_movement = add_rate(pitcher_movement, "swings", "pitches", "swing_rate")
pitcher_movement = add_rate(pitcher_movement, "whiffs", "swings", "whiff_per_swing")
pitcher_movement = add_rate(pitcher_movement, "chases", "out_zone_pitches", "chase_rate_generated")

pitcher_movement = round_existing(
    pitcher_movement,
    ["avg_velocity", "avg_h_mov", "avg_v_mov"]
)

pitcher_movement = pitcher_movement.sort_values(
    ["player_name", "pitches"],
    ascending=[True, False]
)

pitcher_movement.to_csv(
    tables_dir / f"{DATE}-pitcher-movement-by-side.csv",
    index=False
)

# =========================
# 2) Pitcher contact allowed
# =========================

pitcher_contact = (
    tor_pitching[tor_pitching["is_bbe"]]
    .groupby(["player_name", "pitch_type", "stand"])
    .agg(
        bbe=("is_bbe", "sum"),
        avg_ev=("launch_speed", "mean"),
        max_ev=("launch_speed", "max"),
        avg_la=("launch_angle", "mean"),
        hard_hits=("is_hard_hit", "sum"),
        barrels=("is_barrel", "sum"),
        sweet_spots=("is_sweet_spot", "sum"),
    )
    .reset_index()
)

pitcher_contact = add_rate(pitcher_contact, "hard_hits", "bbe", "hard_hit_rate")
pitcher_contact = add_rate(pitcher_contact, "barrels", "bbe", "barrel_rate")
pitcher_contact = add_rate(pitcher_contact, "sweet_spots", "bbe", "sweet_spot_rate")

pitcher_contact = round_existing(
    pitcher_contact,
    ["avg_ev", "max_ev", "avg_la"]
)

pitcher_contact = pitcher_contact.sort_values(
    ["player_name", "bbe"],
    ascending=[True, False]
)

pitcher_contact.to_csv(
    tables_dir / f"{DATE}-pitcher-contact-allowed.csv",
    index=False
)

# =========================
# 3) Batter pitch decisions by pitch type
# =========================

batter_decisions = (
    tor_batting
    .groupby(["batter_name", "pitch_type", "p_throws"])
    .agg(
        pitches=("pitch_type", "count"),
        swings=("is_swing", "sum"),
        takes=("is_take", "sum"),
        whiffs=("is_whiff", "sum"),
        fouls=("is_foul", "sum"),
        balls_in_play=("is_bip", "sum"),
        out_zone_pitches=("is_out_zone", "sum"),
        chases=("is_chase", "sum"),
    )
    .reset_index()
)

batter_decisions = add_rate(batter_decisions, "swings", "pitches", "swing_rate")
batter_decisions = add_rate(batter_decisions, "whiffs", "swings", "whiff_per_swing")
batter_decisions = add_rate(batter_decisions, "chases", "out_zone_pitches", "chase_rate")

batter_decisions = batter_decisions.sort_values(
    ["batter_name", "pitches"],
    ascending=[True, False]
)

batter_decisions.to_csv(
    tables_dir / f"{DATE}-batter-pitch-decisions.csv",
    index=False
)

# =========================
# 4) Batter contact quality
# =========================

batter_contact = (
    tor_batting[tor_batting["is_bbe"]]
    .groupby(["batter_name", "pitch_type", "p_throws"])
    .agg(
        bbe=("is_bbe", "sum"),
        avg_ev=("launch_speed", "mean"),
        max_ev=("launch_speed", "max"),
        avg_la=("launch_angle", "mean"),
        hard_hits=("is_hard_hit", "sum"),
        barrels=("is_barrel", "sum"),
        sweet_spots=("is_sweet_spot", "sum"),
    )
    .reset_index()
)

batter_contact = add_rate(batter_contact, "hard_hits", "bbe", "hard_hit_rate")
batter_contact = add_rate(batter_contact, "barrels", "bbe", "barrel_rate")
batter_contact = add_rate(batter_contact, "sweet_spots", "bbe", "sweet_spot_rate")

batter_contact = round_existing(
    batter_contact,
    ["avg_ev", "max_ev", "avg_la"]
)

batter_contact = batter_contact.sort_values(
    ["batter_name", "bbe"],
    ascending=[True, False]
)

batter_contact.to_csv(
    tables_dir / f"{DATE}-batter-contact-quality.csv",
    index=False
)

# =========================
# 5) Situational hitting
# =========================

situational = (
    tor_batting
    .groupby(["batter_name", "base_situation"])
    .agg(
        pitches=("pitch_type", "count"),
        swings=("is_swing", "sum"),
        whiffs=("is_whiff", "sum"),
        fouls=("is_foul", "sum"),
        balls_in_play=("is_bip", "sum"),
        out_zone_pitches=("is_out_zone", "sum"),
        chases=("is_chase", "sum"),
        bbe=("is_bbe", "sum"),
        avg_ev=("launch_speed", "mean"),
        avg_la=("launch_angle", "mean"),
        hard_hits=("is_hard_hit", "sum"),
        barrels=("is_barrel", "sum"),
    )
    .reset_index()
)

situational = add_rate(situational, "swings", "pitches", "swing_rate")
situational = add_rate(situational, "whiffs", "swings", "whiff_per_swing")
situational = add_rate(situational, "chases", "out_zone_pitches", "chase_rate")
situational = add_rate(situational, "hard_hits", "bbe", "hard_hit_rate")
situational = add_rate(situational, "barrels", "bbe", "barrel_rate")

situational = round_existing(
    situational,
    ["avg_ev", "avg_la"]
)

situational = situational.sort_values(
    ["batter_name", "base_situation"]
)

situational.to_csv(
    tables_dir / f"{DATE}-situational-hitting.csv",
    index=False
)

# =========================
# 6) Spray chart raw data
# =========================

spray_data = tor_batting[
    tor_batting["hc_x"].notna() & tor_batting["hc_y"].notna()
][
    [
        "batter_name", "stand", "pitch_type", "p_throws",
        "events", "description", "bb_type",
        "launch_speed", "launch_angle",
        "hc_x", "hc_y"
    ]
].copy()

spray_data.to_csv(
    tables_dir / f"{DATE}-spray-chart-data.csv",
    index=False
)
# =========================
# Final display name cleanup
# =========================

pitcher_movement["player_name"] = pitcher_movement["player_name"].apply(format_name)

if not pitcher_contact.empty:
    pitcher_contact["player_name"] = pitcher_contact["player_name"].apply(format_name)
# =========================
# 7) Markdown advanced report
# =========================

lines = []

lines.append(f"# Toronto Blue Jays Advanced Game Report — {DATE}")
lines.append("")
lines.append("## Data Scope")
lines.append("")
lines.append(
    f"This report uses Statcast pitch-level data for the Toronto Blue Jays game on {DATE}. "
    "It separates Blue Jays pitching and Blue Jays hitting, then summarizes pitch movement, "
    "swing decisions, batted-ball quality, and situational trends."
)
lines.append("")

lines.append("## Key Metric Definitions")
lines.append("")
lines.append("- **H-Mov / V-Mov:** horizontal and vertical pitch movement in inches.")
lines.append("- **Whiff/Swing%:** whiffs divided by swings.")
lines.append("- **Chase Rate:** swings at pitches outside the strike zone.")
lines.append("- **Hard-Hit Rate:** batted balls with exit velocity of 95 mph or higher.")
lines.append("- **Barrel Rate:** batted balls classified as barrels by Statcast launch speed/angle zone.")
lines.append("- **Sweet-Spot Rate:** batted balls with launch angle between 8 and 32 degrees.")
lines.append("")
# =========================
# Game Review Summary
# =========================

total_pitching_pitches = int(tor_pitching.shape[0])
total_batting_pitches = int(tor_batting.shape[0])

total_bbe = int(tor_batting["is_bbe"].sum())
total_hard_hits = int(tor_batting["is_hard_hit"].sum())
total_barrels = int(tor_batting["is_barrel"].sum())

team_hard_hit_rate = 0
team_barrel_rate = 0

if total_bbe > 0:
    team_hard_hit_rate = round(total_hard_hits / total_bbe * 100, 1)
    team_barrel_rate = round(total_barrels / total_bbe * 100, 1)

# Best whiff-generating pitch, small-sample aware
whiff_candidates = pitcher_movement[
    (pitcher_movement["swings"] >= 2) &
    (pitcher_movement["pitches"] >= 2)
].copy()

if not whiff_candidates.empty:
    best_whiff_pitch = whiff_candidates.sort_values(
        "whiff_per_swing",
        ascending=False
    ).iloc[0]
else:
    best_whiff_pitch = None

# Best Blue Jays contact quality
contact_candidates = batter_contact[
    batter_contact["bbe"] >= 1
].copy()

if not contact_candidates.empty:
    best_contact = contact_candidates.sort_values(
        "max_ev",
        ascending=False
    ).iloc[0]
else:
    best_contact = None

# Best plate discipline by chase rate
discipline_candidates = batter_decisions[
    batter_decisions["out_zone_pitches"] >= 2
].copy()

if not discipline_candidates.empty:
    hitter_discipline = (
        discipline_candidates
        .groupby("batter_name")
        .agg(
            out_zone_pitches=("out_zone_pitches", "sum"),
            chases=("chases", "sum"),
            pitches=("pitches", "sum")
        )
        .reset_index()
    )

    hitter_discipline["chase_rate"] = np.where(
        hitter_discipline["out_zone_pitches"] > 0,
        hitter_discipline["chases"] / hitter_discipline["out_zone_pitches"] * 100,
        0
    )

    hitter_discipline["chase_rate"] = hitter_discipline["chase_rate"].round(1)

    best_discipline = hitter_discipline.sort_values(
        ["chase_rate", "out_zone_pitches"],
        ascending=[True, False]
    ).iloc[0]
else:
    best_discipline = None

lines.append("## Game Review Summary")
lines.append("")
lines.append(
    f"This report reviews the Toronto Blue Jays' {DATE} game through Statcast pitch-level data. "
    f"The dataset includes **{total_pitching_pitches} Blue Jays pitching events** and "
    f"**{total_batting_pitches} Blue Jays hitting events**, with a focus on pitch movement, "
    f"swing decisions, batted-ball quality, and situational hitting."
)
lines.append("")

lines.append("## Key Takeaways")
lines.append("")

if best_whiff_pitch is not None:
    lines.append(
        f"1. **Pitching swing-and-miss note:** "
        f"{best_whiff_pitch['player_name']}'s **{best_whiff_pitch['pitch_type']}** "
        f"generated the strongest whiff profile in this sample, producing a "
        f"**{best_whiff_pitch['whiff_per_swing']:.1f}% whiff-per-swing rate** "
        f"on {int(best_whiff_pitch['swings'])} swings."
    )
else:
    lines.append(
        "1. **Pitching swing-and-miss note:** There was not enough swing data to identify a clear whiff pitch."
    )

if best_contact is not None:
    lines.append(
        f"2. **Best contact-quality note:** "
        f"{best_contact['batter_name']} produced the top tracked contact quality in this sample, "
        f"with a max exit velocity of **{best_contact['max_ev']:.1f} mph** "
        f"against **{best_contact['pitch_type']}**."
    )
else:
    lines.append(
        "2. **Best contact-quality note:** There were no tracked batted balls available for contact-quality analysis."
    )

lines.append(
    f"3. **Team contact-quality note:** Blue Jays hitters produced **{total_bbe} tracked batted balls**, "
    f"with a **{team_hard_hit_rate:.1f}% hard-hit rate** and a "
    f"**{team_barrel_rate:.1f}% barrel rate**."
)

if best_discipline is not None:
    lines.append(
        f"4. **Plate-discipline note:** "
        f"{best_discipline['batter_name']} showed the lowest chase rate among hitters with multiple "
        f"out-of-zone pitches in this sample, chasing **{best_discipline['chase_rate']:.1f}%** "
        f"of pitches outside the zone."
    )
else:
    lines.append(
        "4. **Plate-discipline note:** There was not enough out-of-zone pitch data to identify a clear chase-rate leader."
    )

lines.append("")
lines.append(
    "_Note: This is a single-game sample, so the takeaways should be treated as descriptive rather than predictive._"
)
lines.append("")
# Pitching section
lines.append("## Blue Jays Pitching")
lines.append("")
lines.append("## Visual Summary")
lines.append("")

lines.append("### Pitch Movement Plot")
lines.append("")
lines.append(
    "This chart shows the horizontal and vertical movement profile of Blue Jays pitches. "
    "It helps identify how each pitch type separated from the rest of the arsenal."
)
lines.append("")
lines.append(f"![Pitch Movement Plot]({pitch_movement_chart})")
lines.append("")

lines.append("### Exit Velocity vs. Launch Angle")
lines.append("")
lines.append(
    "This chart shows the quality of contact produced by Blue Jays hitters. "
    "The vertical reference lines help separate hard contact and optimal launch-angle ranges."
)
lines.append("")
lines.append(f"![Exit Velocity vs Launch Angle]({ev_la_chart})")
lines.append("")

lines.append("### Spray Chart")
lines.append("")
lines.append(
    "This chart shows where Blue Jays batted balls were hit on the field. "
    "It provides an initial view of pull-side, middle-field, and opposite-field contact distribution."
)
lines.append("")
lines.append(f"![Spray Chart]({spray_chart})")
lines.append("")
for pitcher in pitcher_movement["player_name"].dropna().unique():
    lines.append(f"### {pitcher}")
    lines.append("")

    pm = pitcher_movement[pitcher_movement["player_name"] == pitcher].copy()
    pc = pitcher_contact[pitcher_contact["player_name"] == pitcher].copy()

    total_pitches = int(pm["pitches"].sum())
    lines.append(f"{pitcher} threw **{total_pitches} tracked pitches**.")
    lines.append("")

    lines.append("#### Pitch Movement and Swing Profile")
    lines.append("")
    lines += md_table(
        pm,
        [
            "pitch_type", "stand", "pitches", "avg_velocity",
            "avg_h_mov", "avg_v_mov",
            "swing_rate", "whiff_per_swing", "chase_rate_generated"
        ],
        max_rows=12
    )

    if not pc.empty:
        lines.append("#### Contact Allowed")
        lines.append("")
        lines += md_table(
            pc,
            [
                "pitch_type", "stand", "bbe",
                "avg_ev", "max_ev", "avg_la",
                "hard_hit_rate", "barrel_rate", "sweet_spot_rate"
            ],
            max_rows=12
        )

    # Auto insight
    primary = pm.sort_values("pitches", ascending=False).iloc[0]
    lines.append(
        f"**Automated note:** {pitcher}'s most-used pitch was the "
        f"**{primary['pitch_type']}**, accounting for {int(primary['pitches'])} tracked pitches. "
        f"It averaged {primary['avg_velocity']:.1f} mph with "
        f"{primary['avg_h_mov']:.1f} inches of horizontal movement and "
        f"{primary['avg_v_mov']:.1f} inches of vertical movement."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

# Hitting section
lines.append("## Blue Jays Hitting")
lines.append("")

for batter in batter_decisions["batter_name"].dropna().unique():
    bd = batter_decisions[batter_decisions["batter_name"] == batter].copy()
    bc = batter_contact[batter_contact["batter_name"] == batter].copy()

    total_pitches_seen = int(bd["pitches"].sum())

    if total_pitches_seen < 3:
        continue

    lines.append(f"### {batter}")
    lines.append("")
    lines.append(f"{batter} saw **{total_pitches_seen} tracked pitches**.")
    lines.append("")

    lines.append("#### Pitch-Type Decisions")
    lines.append("")
    lines += md_table(
        bd,
        [
            "pitch_type", "p_throws", "pitches",
            "swings", "takes", "whiffs", "fouls", "balls_in_play",
            "swing_rate", "whiff_per_swing", "chase_rate"
        ],
        max_rows=10
    )

    if not bc.empty:
        lines.append("#### Contact Quality")
        lines.append("")
        lines += md_table(
            bc,
            [
                "pitch_type", "p_throws", "bbe",
                "avg_ev", "max_ev", "avg_la",
                "hard_hit_rate", "barrel_rate", "sweet_spot_rate"
            ],
            max_rows=10
        )

    lines.append("---")
    lines.append("")

# Situational hitting
lines.append("## Situational Hitting")
lines.append("")
lines.append("This section compares Blue Jays hitters with runners on base versus no runners on base.")
lines.append("")

lines += md_table(
    situational,
    [
        "batter_name", "base_situation", "pitches",
        "swings", "whiffs", "fouls", "balls_in_play",
        "chase_rate", "avg_ev", "avg_la",
        "hard_hit_rate", "barrel_rate"
    ],
    max_rows=40
)

# Spray data note
lines.append("## Spray Chart Data")
lines.append("")
lines.append(
    f"Spray chart raw data was saved to `reports/tables/{DATE}-spray-chart-data.csv`. "
    "The next step is to turn `hc_x` and `hc_y` into a visual spray chart."
)
lines.append("")

lines.append("## Next Development Steps")
lines.append("")
lines.append("- Add movement scatter plots for each pitcher.")
lines.append("- Add exit velocity vs. launch angle charts for batted balls.")
lines.append("- Add spray charts for Blue Jays hitters.")
lines.append("- Add game context: inning, count, score, leverage, and result.")
lines.append("- Add rolling multi-game trends instead of single-game-only analysis.")
lines.append("")

output_report.write_text("\n".join(lines), encoding="utf-8")

print("Advanced report created!")
print(f"Saved to: {output_report}")
print(f"Tables saved to: {tables_dir}")