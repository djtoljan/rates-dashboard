"""Auto-update rates: run update_rates.py, git commit, git push"""
import subprocess, sys, os

DIR = r"C:\Users\Mi Gaming\.openclaw\workspace\dashboards\gh-pages"
LOG = os.path.join(DIR, "auto_update.log")

def log(msg: str):
    from datetime import datetime
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run(cmd, cwd=DIR):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", str(e)

log("Starting rates update...")

# 1. Pull latest
# Ensure on main branch (not detached HEAD)
code, out, err = run(["git", "checkout", "main"])
if code != 0:
    log(f"CHECKOUT MAIN: {out or err}")
    code, out, err = run(["git", "checkout", "-b", "main"])
    log(f"CHECKOUT -B MAIN: {out or err}")

# Pull latest
code, out, err = run(["git", "pull", "--rebase", "origin", "main"])
log(f"PULL: {out or err}")
if "rebase" in err.lower() or "rebase" in out.lower():
    run(["git", "rebase", "--abort"])
    log("Rebase aborted, trying merge...")
    code, out, err = run(["git", "pull", "origin", "main", "--no-rebase"])
    log(f"PULL MERGE: {out or err}")

# 2. Run update_rates.py
code, out, err = run([sys.executable, "update_rates.py"])
log(f"UPDATE: {out[:300] if out else err[:300]}")

# 3. Stage & commit
code, out, err = run(["git", "add", "rates.json"])
code3, out3, err3 = run(["git", "commit", "-m", "rates auto-update"])
log(f"COMMIT: {out3 or err3 or 'no changes'}")

# 4. Push if committed
if code3 == 0:
    code, out, err = run(["git", "push"])
    log(f"PUSH: {out or err}")

log("Done.")
