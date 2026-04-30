from pathlib import Path
import pandas as pd

# =========================
# Settings
# =========================

DATE = "2026-04-28"

# =========================
# Paths
# =========================

base_dir = Path(__file__).resolve().parents[1]

pitcher_summary_file = base_dir / "reports" / f"{DATE}-pitcher-summary.csv"
output_file = base_dir / "reports" / f"{DATE}-bluejays-game-report.md"

# =========================
# Load data
# =========================

summary = pd.read_csv(pitcher_summary_file)

# Replace missing whiff rates with 0
summary["whiff_rate"] = summary["whiff_rate"].fillna(0)

# =========================
# Pitch type names
# =========================

pitch_names = {
    "FF": "four-seam fastball",
    "SI": "sinker",
    "SL": "slider",
    "ST": "sweeper",
    "CH": "changeup",
    "FS": "splitter",
    "FC": "cutter",
    "CU": "curveball",
    "KC": "knuckle curve",
}

def pitch_name(code):
    return pitch_names.get(code, code)

# =========================
# Generate report
# =========================

lines = []

lines.append(f"# Toronto Blue Jays Daily Game Report — {DATE}")
lines.append("")
lines.append("## Pitching Overview")
lines.append("")
lines.append(
    "This report summarizes Toronto Blue Jays pitchers using Statcast pitch-level data. "
    "The focus is on pitch usage, velocity, movement profile, whiff generation, and balls in play."
)
lines.append("")

# Group by pitcher
for pitcher, group in summary.groupby("player_name"):
    lines.append(f"### {pitcher}")
    lines.append("")

    total_pitches = int(group["pitches"].sum())
    lines.append(f"{pitcher} threw **{total_pitches} tracked pitches** in this game.")
    lines.append("")

    # Pitch table
    lines.append("| Pitch | Count | Avg Velo | H-Mov | V-Mov | Swings | Whiffs | BIP | Whiff% |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for _, row in group.iterrows():
        ptype = pitch_name(row["pitch_type"])
        lines.append(
            f"| {ptype} | "
            f"{int(row['pitches'])} | "
            f"{row['avg_velocity']:.1f} | "
            f"{row['avg_h_mov']:.1f} | "
            f"{row['avg_v_mov']:.1f} | "
            f"{int(row['swings'])} | "
            f"{int(row['whiffs'])} | "
            f"{int(row['balls_in_play'])} | "
            f"{row['whiff_rate']:.1f}% |"
        )

    lines.append("")

    # Main pitch
    main_pitch = group.sort_values("pitches", ascending=False).iloc[0]
    main_pitch_name = pitch_name(main_pitch["pitch_type"])

    lines.append(
        f"**Primary pitch:** {pitcher} relied most heavily on the "
        f"**{main_pitch_name}**, throwing it {int(main_pitch['pitches'])} times."
    )

    lines.append(
        f"It averaged **{main_pitch['avg_velocity']:.1f} mph**, with "
        f"**{main_pitch['avg_h_mov']:.1f} inches of horizontal movement** and "
        f"**{main_pitch['avg_v_mov']:.1f} inches of vertical movement**."
    )

    # Best whiff pitch among pitches with at least 2 swings
    whiff_candidates = group[group["swings"] >= 2]

    if not whiff_candidates.empty:
        best_whiff = whiff_candidates.sort_values("whiff_rate", ascending=False).iloc[0]
        best_whiff_name = pitch_name(best_whiff["pitch_type"])

        lines.append(
            f"The best whiff-generating pitch was the **{best_whiff_name}**, "
            f"which produced a **{best_whiff['whiff_rate']:.1f}% whiff rate** "
            f"on {int(best_whiff['swings'])} swings."
        )

    lines.append("")
    lines.append("---")
    lines.append("")

lines.append("## Initial Takeaways")
lines.append("")
lines.append("- Pitch usage and movement profiles are the first layer of evaluation.")
lines.append("- Future versions of this report will add batter swing decisions, chase rate, barrel rate, launch angle, exit velocity, and spray chart analysis.")
lines.append("- The goal is to build a repeatable daily workflow for evaluating Blue Jays games through Statcast data.")
lines.append("")

# =========================
# Save report
# =========================

output_file.write_text("\n".join(lines), encoding="utf-8")

print("English game report created!")
print(f"Saved to: {output_file}")