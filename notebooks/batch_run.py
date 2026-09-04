import os, subprocess, sys
from datetime import datetime, timedelta

START = datetime(2026, 6, 30)
END   = datetime(2026, 9, 3)
NB    = 'game_report_template.ipynb'

W, L = 40, 44   # 6/29 종료 시점 기록
cur = START
while cur <= END:
    d = cur.strftime('%Y-%m-%d')
    print("=== " + d + " ===")
    env = dict(os.environ, BJ_AUTO_DATE=d, BJ_W=str(W), BJ_L=str(L))
    r = subprocess.run(
        ['jupyter', 'nbconvert', '--to', 'notebook', '--execute',
         '--ExecutePreprocessor.timeout=600', NB,
         '--output', 'batch_tmp.ipynb'],
        env=env, capture_output=True, text=True)
    if 'NO_TOR_GAME' in r.stderr or 'NO_TOR_GAME' in r.stdout:
        print("  no game")
    elif r.returncode != 0:
        print("  ERROR:\n" + r.stderr[-1500:])
    else:
        # 결과 파일에서 W/L 읽어서 누적
        with open('../data/report_data_' + d + '.txt') as f:
            for line in f:
                if line.startswith('Result:'):
                    W += line.split()[1] == 'W'
                    L += line.split()[1] == 'L'
                    print("  " + line.strip() + " -> " + str(W) + "-" + str(L))
                    break
    cur += timedelta(days=1)

if os.path.exists('batch_tmp.ipynb'):
    os.remove('batch_tmp.ipynb')
print("DONE")