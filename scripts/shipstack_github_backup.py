
@mcp.tool()
def shipstack_github_backup(message: str = "") -> dict:
    """Backup ShipStack repo to GitHub. One call: git add -A, commit, push.

    Targets C:\\Users\\integ\\Documents\\Claude\\Projects\\Drop shipping\\
    (the ShipStack/dropship-os repo, NOT Quinn).

    Honors .gitignore (.env, .backups/, *.cred.xml stay local).

    Args:
        message: Optional commit message. Defaults to 'shipstack auto-backup YYYY-MM-DD HH:MM:SS'.

    Returns:
        {status, commit_sha, files_changed, push_result, message}
    """
    import subprocess
    from datetime import datetime

    repo = r"C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os"
    git = r"C:\Program Files\Git\cmd\git.exe"

    if not message:
        message = f"shipstack auto-backup {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    def run(args, timeout=60):
        try:
            r = subprocess.run([git] + args, cwd=repo, capture_output=True,
                               text=True, timeout=timeout)
            return {"ok": r.returncode == 0, "stdout": r.stdout.strip(),
                    "stderr": r.stderr.strip(), "code": r.returncode}
        except Exception as e:
            return {"ok": False, "stdout": "", "stderr": str(e), "code": -1}

    add = run(["add", "-A"])
    if not add["ok"]:
        return {"status": "failed", "stage": "add", "error": add["stderr"]}

    status_check = run(["status", "--porcelain"])
    files_changed = len([l for l in status_check["stdout"].splitlines() if l.strip()])

    if files_changed == 0:
        return {"status": "nothing_to_commit", "commit_sha": None,
                "files_changed": 0, "message": message}

    commit = run(["commit", "-m", message])
    if not commit["ok"]:
        return {"status": "failed", "stage": "commit",
                "error": commit["stderr"] or commit["stdout"]}

    sha_r = run(["rev-parse", "--short", "HEAD"])
    sha = sha_r["stdout"] if sha_r["ok"] else "unknown"

    push = run(["push", "origin", "main"], timeout=120)

    try:
        _auto_log("shipstack_github_backup", repo, "backup",
                  f"sha={sha} files={files_changed} push_ok={push['ok']}")
    except Exception:
        pass

    return {
        "status": "ok" if push["ok"] else "committed_not_pushed",
        "commit_sha": sha,
        "files_changed": files_changed,
        "push_result": push["stderr"] or push["stdout"] or "pushed",
        "message": message,
    }
