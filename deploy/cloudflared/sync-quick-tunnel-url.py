#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TRYCLOUDFLARE_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
DEFAULT_GIT_COMMIT_MESSAGE = "docs: refresh live demo URL"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync the latest Cloudflare Quick Tunnel URL into local files."
    )
    parser.add_argument("--repo-root", default=os.environ.get("CAREER_COUNSEL_REPO_ROOT"))
    parser.add_argument(
        "--backend-env",
        default=os.environ.get("CAREER_COUNSEL_BACKEND_ENV"),
    )
    parser.add_argument(
        "--readme",
        default=os.environ.get("CAREER_COUNSEL_README_PATH"),
    )
    parser.add_argument(
        "--quick-tunnel-unit",
        default=os.environ.get(
            "CAREER_COUNSEL_QUICK_TUNNEL_UNIT", "cloudflared-quick.service"
        ),
    )
    parser.add_argument(
        "--api-service",
        default=os.environ.get("CAREER_COUNSEL_API_SERVICE", "counsel-api.service"),
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=int(os.environ.get("CAREER_COUNSEL_WAIT_SECONDS", "60")),
    )
    parser.add_argument(
        "--git-push-delay-seconds",
        type=int,
        default=int(os.environ.get("CAREER_COUNSEL_GIT_PUSH_DELAY_SECONDS", "10")),
    )
    parser.add_argument(
        "--git-remote",
        default=os.environ.get("CAREER_COUNSEL_GIT_REMOTE", "origin"),
    )
    parser.add_argument(
        "--git-branch",
        default=os.environ.get("CAREER_COUNSEL_GIT_BRANCH", "main"),
    )
    parser.add_argument(
        "--git-commit-message",
        default=os.environ.get(
            "CAREER_COUNSEL_GIT_COMMIT_MESSAGE", DEFAULT_GIT_COMMIT_MESSAGE
        ),
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("CAREER_COUNSEL_TUNNEL_URL"),
        help="Override the detected trycloudflare URL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("CAREER_COUNSEL_DRY_RUN", "").lower() == "true",
    )
    parser.add_argument(
        "--git-auto-push",
        action="store_true",
        default=os.environ.get("CAREER_COUNSEL_GIT_AUTO_PUSH", "").lower() == "true",
    )
    parser.add_argument("--skip-restart-api", action="store_true")
    return parser.parse_args()


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def detect_tunnel_url(unit: str, wait_seconds: int) -> str:
    deadline = time.time() + wait_seconds
    while time.time() <= deadline:
        completed = subprocess.run(
            ["journalctl", "-u", unit, "--no-pager", "-b", "-n", "200"],
            check=False,
            capture_output=True,
            text=True,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        matches = TRYCLOUDFLARE_URL_RE.findall(output)
        if matches:
            return matches[-1]
        time.sleep(1)

    raise RuntimeError(
        f"Could not find a trycloudflare URL in journal entries for {unit!r}."
    )


def atomic_write(path: Path, content: str) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def update_readme(readme_path: Path, new_url: str) -> bool:
    content = readme_path.read_text(encoding="utf-8")
    updated = TRYCLOUDFLARE_URL_RE.sub(new_url, content)
    if updated == content:
        return False

    atomic_write(readme_path, updated)
    return True


def replace_or_append_env_value(content: str, key: str, value: str) -> tuple[str, bool]:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    replacement = f"{key}={value}"
    if pattern.search(content):
        updated = pattern.sub(replacement, content, count=1)
        return updated, updated != content

    newline = "\n" if content and not content.endswith("\n") else ""
    updated = f"{content}{newline}{replacement}\n"
    return updated, True


def merge_cors_origins(current_value: str, new_url: str) -> str:
    entries = [entry.strip() for entry in current_value.split(",") if entry.strip()]
    merged: list[str] = []
    inserted = False

    for entry in entries:
        if TRYCLOUDFLARE_URL_RE.fullmatch(entry):
            if not inserted:
                merged.append(new_url)
                inserted = True
            continue

        if entry not in merged:
            merged.append(entry)

    if not inserted and new_url not in merged:
        merged.append(new_url)

    return ",".join(merged or [new_url])


def update_backend_env(env_path: Path, new_url: str) -> bool:
    content = env_path.read_text(encoding="utf-8")
    changed = False

    updated, did_change = replace_or_append_env_value(
        content,
        "COUNSEL_FRONTEND_APP_URL",
        new_url,
    )
    content = updated
    changed = changed or did_change

    cors_match = re.search(r"^COUNSEL_API_CORS_ORIGINS=(.*)$", content, re.MULTILINE)
    current_cors = cors_match.group(1) if cors_match else ""
    merged_cors = merge_cors_origins(current_cors, new_url)
    updated, did_change = replace_or_append_env_value(
        content,
        "COUNSEL_API_CORS_ORIGINS",
        merged_cors,
    )
    content = updated
    changed = changed or did_change

    if changed:
        atomic_write(env_path, content)

    return changed


def restart_api_service(service_name: str) -> bool:
    if not service_name:
        return False
    result = run_command(["sudo", "systemctl", "restart", service_name], check=False)
    if result.returncode != 0:
        print(
            f"WARNING: Failed to restart {service_name} (exit {result.returncode}). "
            f"stderr: {result.stderr.strip()}"
        )
        return False
    return True


def relative_repo_path(repo_root: Path, path: Path) -> Path:
    return path.resolve().relative_to(repo_root.resolve())


def has_staged_changes(repo_root: Path) -> bool:
    completed = run_command(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_root,
        check=False,
    )
    return completed.returncode != 0


def commit_and_push_readme(
    *,
    repo_root: Path,
    readme_path: Path,
    remote: str,
    branch: str,
    delay_seconds: int,
    commit_message: str,
    dry_run: bool,
) -> bool:
    relative_readme = relative_repo_path(repo_root, readme_path)

    if dry_run:
        print(
            f"[dry-run] would wait {delay_seconds}s then commit and push {relative_readme}"
        )
        print(f"[dry-run] would run: git push {remote} HEAD:{branch}")
        return False

    if delay_seconds > 0:
        time.sleep(delay_seconds)

    if has_staged_changes(repo_root):
        print(
            "Skipped README auto-push because the repository already has staged changes."
        )
        return False

    run_command(["git", "add", "--", str(relative_readme)], cwd=repo_root)

    staged_readme = run_command(
        ["git", "diff", "--cached", "--quiet", "--", str(relative_readme)],
        cwd=repo_root,
        check=False,
    )
    if staged_readme.returncode == 0:
        print("Skipped README auto-push because there is no staged README change.")
        return False

    run_command(
        ["git", "commit", "-m", commit_message, "--", str(relative_readme)],
        cwd=repo_root,
    )
    run_command(["git", "push", remote, f"HEAD:{branch}"], cwd=repo_root)
    return True


def resolve_path(value: str | None, fallback: Path | None = None) -> Path:
    if value:
        return Path(value).resolve()
    if fallback is not None:
        return fallback.resolve()
    raise ValueError("Missing required path configuration.")


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    backend_env = resolve_path(
        args.backend_env,
        repo_root / "backend/.env" if repo_root else None,
    )
    readme_path = resolve_path(
        args.readme,
        repo_root / "README.md" if repo_root else None,
    )
    if repo_root is None:
        repo_root = readme_path.parent

    url = args.url or detect_tunnel_url(args.quick_tunnel_unit, args.wait_seconds)

    if not TRYCLOUDFLARE_URL_RE.fullmatch(url):
        raise ValueError(f"Unexpected tunnel URL format: {url}")

    if args.dry_run:
        print(f"[dry-run] detected tunnel URL: {url}")
        print(f"[dry-run] would update {backend_env}")
        print(f"[dry-run] would update {readme_path}")
        if not args.skip_restart_api:
            print(f"[dry-run] would restart {args.api_service}")
    else:
        backend_changed = update_backend_env(backend_env, url)
        readme_changed = update_readme(readme_path, url)

        api_restarted = False
        if backend_changed and not args.skip_restart_api:
            api_restarted = restart_api_service(args.api_service)

        readme_pushed = False
        if readme_changed and args.git_auto_push:
            readme_pushed = commit_and_push_readme(
                repo_root=repo_root,
                readme_path=readme_path,
                remote=args.git_remote,
                branch=args.git_branch,
                delay_seconds=args.git_push_delay_seconds,
                commit_message=args.git_commit_message,
                dry_run=args.dry_run,
            )

        print(f"Synced Quick Tunnel URL: {url}")
        print(f"backend/.env updated: {'yes' if backend_changed else 'no'}")
        print(f"README.md updated: {'yes' if readme_changed else 'no'}")
        if backend_changed and not args.skip_restart_api:
            print(f"Restarted API service: {'yes' if api_restarted else 'FAILED (non-fatal)'}")
        if readme_changed and args.git_auto_push:
            print(f"README auto-pushed: {'yes' if readme_pushed else 'no'}")
        return 0

    if args.git_auto_push:
        commit_and_push_readme(
            repo_root=repo_root,
            readme_path=readme_path,
            remote=args.git_remote,
            branch=args.git_branch,
            delay_seconds=args.git_push_delay_seconds,
            commit_message=args.git_commit_message,
            dry_run=True,
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI safety net
        print(f"quick tunnel sync failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
