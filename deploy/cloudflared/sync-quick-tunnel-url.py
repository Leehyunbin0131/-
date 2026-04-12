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
        "--url",
        default=os.environ.get("CAREER_COUNSEL_TUNNEL_URL"),
        help="Override the detected trycloudflare URL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("CAREER_COUNSEL_DRY_RUN", "").lower() == "true",
    )
    parser.add_argument("--skip-restart-api", action="store_true")
    return parser.parse_args()


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def detect_tunnel_url(unit: str, wait_seconds: int) -> str:
    deadline = time.time() + wait_seconds
    while time.time() <= deadline:
        completed = subprocess.run(
            ["journalctl", "-u", unit, "--no-pager", "-n", "200"],
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


def restart_api_service(service_name: str) -> None:
    if not service_name:
        return
    run_command(["systemctl", "restart", service_name])


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

    url = args.url or detect_tunnel_url(args.quick_tunnel_unit, args.wait_seconds)

    if not TRYCLOUDFLARE_URL_RE.fullmatch(url):
        raise ValueError(f"Unexpected tunnel URL format: {url}")

    if args.dry_run:
        print(f"[dry-run] detected tunnel URL: {url}")
        print(f"[dry-run] would update {backend_env}")
        print(f"[dry-run] would update {readme_path}")
        if not args.skip_restart_api:
            print(f"[dry-run] would restart {args.api_service}")
        return 0

    backend_changed = update_backend_env(backend_env, url)
    readme_changed = update_readme(readme_path, url)

    if backend_changed and not args.skip_restart_api:
        restart_api_service(args.api_service)

    print(f"Synced Quick Tunnel URL: {url}")
    print(f"backend/.env updated: {'yes' if backend_changed else 'no'}")
    print(f"README.md updated: {'yes' if readme_changed else 'no'}")
    if backend_changed and not args.skip_restart_api:
        print(f"Restarted API service: {args.api_service}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI safety net
        print(f"quick tunnel sync failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
