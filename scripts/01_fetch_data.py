from pybaseball import statcast
from pathlib import Path
import pandas as pd

# =========================
# 설정
# =========================

TEAM = "TOR"          # Toronto Blue Jays
DATE = "2026-04-28"  # 일단 테스트 날짜. 경기 없는 날이면 다른 날짜로 바꾸면 됩니다.

# =========================
# 폴더 준비
# =========================

base_dir = Path(__file__).resolve().parents[1]
data_dir = base_dir / "data"
data_dir.mkdir(exist_ok=True)

output_file = data_dir / f"{DATE}-bluejays-statcast.csv"

# =========================
# 데이터 다운로드
# =========================

print(f"Downloading Statcast data for {TEAM} on {DATE}...")

# Download all Statcast data for the date, then keep only the Blue Jays game.
# This is important because team="TOR" can return only one side of the game.
all_df = statcast(start_dt=DATE, end_dt=DATE)

df = all_df[
    (all_df["home_team"] == TEAM) |
    (all_df["away_team"] == TEAM)
].copy()

# =========================
# 저장
# =========================

df.to_csv(output_file, index=False)

print("Done!")
print(f"Saved to: {output_file}")
print(f"Rows: {len(df)}")
print("Columns:")
print(df.columns.tolist())