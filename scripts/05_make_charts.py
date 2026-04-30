from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

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

charts_dir = base_dir / "charts" / DATE
charts_dir.mkdir(parents=True, exist_ok=True)

# =========================
# Load data
# =========================

df = pd.read_csv(data_file)

# =========================
# Helper functions
# =========================

def format_name(name):
    if pd.isna(name):
        return "Unknown"

    name = str(name).strip()

    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}"

    return name


# =========================
# Basic cleaning
# =========================

df["player_name"] = df["player_name"].apply(format_name)

numeric_cols = [
    "release_speed", "pfx_x", "pfx_z",
    "launch_speed", "launch_angle",
    "hc_x", "hc_y"
]

for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# =========================
# Identify Blue Jays batting / pitching
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
# Movement columns
# =========================
# Statcast pfx_x and pfx_z are in feet.
# Convert them to inches.
# h_mov_in is flipped to show horizontal movement from the pitcher's perspective.

tor_pitching["h_mov_in"] = -12 * tor_pitching["pfx_x"]
tor_pitching["v_mov_in"] = 12 * tor_pitching["pfx_z"]

# =========================
# Chart 1: Pitch Movement Plot
# =========================

movement_data = tor_pitching[
    tor_pitching["h_mov_in"].notna() &
    tor_pitching["v_mov_in"].notna() &
    tor_pitching["pitch_type"].notna()
].copy()

plt.figure(figsize=(9, 7))

for pitch_type, group in movement_data.groupby("pitch_type"):
    plt.scatter(
        group["h_mov_in"],
        group["v_mov_in"],
        label=pitch_type,
        alpha=0.75
    )

plt.axhline(0, linewidth=1)
plt.axvline(0, linewidth=1)

plt.title(f"Blue Jays Pitch Movement — {DATE}")
plt.xlabel("Horizontal Movement, inches")
plt.ylabel("Vertical Movement, inches")
plt.legend(title="Pitch Type")
plt.grid(True, alpha=0.3)
plt.tight_layout()

pitch_movement_file = charts_dir / f"{DATE}-pitch-movement.png"
plt.savefig(pitch_movement_file, dpi=200)
plt.close()

# =========================
# Chart 2: Exit Velocity vs Launch Angle
# =========================

bbe = tor_batting[
    tor_batting["launch_speed"].notna() &
    tor_batting["launch_angle"].notna()
].copy()

plt.figure(figsize=(9, 7))

for bb_type, group in bbe.groupby("bb_type"):
    plt.scatter(
        group["launch_speed"],
        group["launch_angle"],
        label=bb_type,
        alpha=0.75
    )

plt.axvline(95, linewidth=1, linestyle="--")
plt.axhline(8, linewidth=1, linestyle="--")
plt.axhline(32, linewidth=1, linestyle="--")

plt.title(f"Blue Jays Batted Ball Quality — {DATE}")
plt.xlabel("Exit Velocity, mph")
plt.ylabel("Launch Angle, degrees")
plt.legend(title="Batted Ball Type")
plt.grid(True, alpha=0.3)
plt.tight_layout()

ev_la_file = charts_dir / f"{DATE}-exit-velocity-launch-angle.png"
plt.savefig(ev_la_file, dpi=200)
plt.close()

# =========================
# Chart 3: Spray Chart
# =========================

spray = tor_batting[
    tor_batting["hc_x"].notna() &
    tor_batting["hc_y"].notna()
].copy()

plt.figure(figsize=(8, 8))

for bb_type, group in spray.groupby("bb_type"):
    plt.scatter(
        group["hc_x"],
        group["hc_y"],
        label=bb_type,
        alpha=0.75
    )

plt.title(f"Blue Jays Spray Chart — {DATE}")
plt.xlabel("Horizontal Contact Coordinate")
plt.ylabel("Vertical Contact Coordinate")
plt.legend(title="Batted Ball Type")
plt.grid(True, alpha=0.3)

# Baseball Savant coordinates are easier to view with the y-axis inverted.
plt.gca().invert_yaxis()

plt.tight_layout()

spray_file = charts_dir / f"{DATE}-spray-chart.png"
plt.savefig(spray_file, dpi=200)
plt.close()

# =========================
# Done
# =========================

print("Charts created!")
print(f"Saved to: {charts_dir}")
print()
print(f"1. {pitch_movement_file}")
print(f"2. {ev_la_file}")
print(f"3. {spray_file}")