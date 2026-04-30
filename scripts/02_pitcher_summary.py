from pathlib import Path
import pandas as pd

# =========================
# 설정
# =========================

DATE = "2026-04-28"

# =========================
# 경로 설정
# =========================

base_dir = Path(__file__).resolve().parents[1]
data_file = base_dir / "data" / f"{DATE}-bluejays-statcast.csv"

reports_dir = base_dir / "reports"
reports_dir.mkdir(exist_ok=True)

output_file = reports_dir / f"{DATE}-pitcher-summary.csv"

# =========================
# 데이터 읽기
# =========================

df = pd.read_csv(data_file)

# =========================
# 이름 표시 형식 변경
# "Fluharty, Mason" -> "Mason Fluharty"
# =========================

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
# 무브먼트 계산
# =========================
# pfx_x, pfx_z는 feet 단위라서 inch로 바꿉니다.
# h_mov_in: 수평 무브먼트
# v_mov_in: 수직 무브먼트

df["h_mov_in"] = -12 * df["pfx_x"]
df["v_mov_in"] = 12 * df["pfx_z"]

# =========================
# 스윙 / 헛스윙 / 인플레이 표시
# =========================

swing_descriptions = [
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
]

whiff_descriptions = [
    "swinging_strike",
    "swinging_strike_blocked",
]

in_play_descriptions = [
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
]

df["is_swing"] = df["description"].isin(swing_descriptions)
df["is_whiff"] = df["description"].isin(whiff_descriptions)
df["is_in_play"] = df["description"].isin(in_play_descriptions)

# =========================
# 투수별 / 구종별 요약
# =========================

summary = (
    df.groupby(["player_name", "pitch_type"])
    .agg(
        pitches=("pitch_type", "count"),
        avg_velocity=("release_speed", "mean"),
        avg_h_mov=("h_mov_in", "mean"),
        avg_v_mov=("v_mov_in", "mean"),
        swings=("is_swing", "sum"),
        whiffs=("is_whiff", "sum"),
        balls_in_play=("is_in_play", "sum"),
    )
    .reset_index()
)

# 헛스윙률 계산
summary["whiff_rate"] = summary["whiffs"] / summary["swings"]
summary["whiff_rate"] = summary["whiff_rate"].fillna(0)
# 보기 좋게 반올림
summary["avg_velocity"] = summary["avg_velocity"].round(1)
summary["avg_h_mov"] = summary["avg_h_mov"].round(1)
summary["avg_v_mov"] = summary["avg_v_mov"].round(1)
summary["whiff_rate"] = (summary["whiff_rate"] * 100).round(1)

# 투구수 많은 순서로 정렬
summary = summary.sort_values(
    by=["player_name", "pitches"],
    ascending=[True, False]
)

# =========================
# 저장 및 출력
# =========================

summary.to_csv(output_file, index=False)

print("Pitcher summary created!")
print(f"Saved to: {output_file}")
print()
print(summary)