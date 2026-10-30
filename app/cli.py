"""Command line entry point (`uv run bub ...`, wrapped by the Makefile).

  bub tasks                                   list available tasks
  bub run <task> [-i key=value ...]           run one task
        [--mode installed|fresh] [--headless|--headed] [--json]
  bub chrome start|stop|status                Mode 1: manage the installed Chrome with a CDP port
  bub copy-profile --source DIR --profile "Profile 1"
                                              Mode 1: copy an everyday Chrome profile into CHROME_USER_DATA_DIR
  bub doctor                                  check keys, browsers, ports
  bub cost                                    today's LLM spend
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import platform
import sys
from dataclasses import replace
from pathlib import Path

from app.config import Settings


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level, logging.INFO),
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")


def _parse_inputs(pairs: list[str]) -> dict:
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise SystemExit(f"--input must be key=value, got '{p}'")
        k, v = p.split("=", 1)
        out[k.strip()] = v
    return out


def _settings_from_args(args) -> Settings:
    s = Settings.from_env()
    if getattr(args, "headless", None) is not None:
        s = replace(s, headless=args.headless)
    return s


def cmd_tasks(args) -> int:
    from app.tasks import all_tasks

    for name, cls in all_tasks().items():
        req = ", ".join(cls.required_inputs) or "-"
        opt = ", ".join(f"{k}={v}" for k, v in cls.optional_inputs.items()) or "-"
        print(f"{name:<20} {cls.description}\n{'':<20} required: {req} | optional: {opt}")
    return 0


def cmd_run(args) -> int:
    from app.runner import run_task

    settings = _settings_from_args(args)
    inputs = _parse_inputs(args.input)
    result = asyncio.run(run_task(args.task, inputs=inputs, mode=args.mode, settings=settings))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str, ensure_ascii=False))
    else:
        print(f"\nstatus : {result.status}   mode: {result.mode}   steps: {result.steps}   "
              f"time: {result.duration_sec}s   cost: ${result.usage.get('cost_usd', 0):.5f}")
        if result.error:
            print(f"error  : {result.error}")
        print("output :", json.dumps(result.output, indent=2, default=str, ensure_ascii=False)
              if not isinstance(result.output, str) else result.output)
        if result.screenshot:
            print(f"shot   : {result.screenshot}")
    return 0 if result.ok else 1


def cmd_chrome(args) -> int:
    from app.browser import cdp, installed

    s = _settings_from_args(args)
    if args.action == "start":
        s = replace(s, installed_action="launch")
        url = installed.ensure_chrome(s)
        print(f"Chrome ready on {url}  (profile: {s.chrome_user_data_dir})")
        print("Log in to the sites you need in this window; the session is kept for later runs.")
    elif args.action == "stop":
        print("stopped" if installed.close_chrome(s) else "no Chrome started by this tool (no pid file)")
    else:
        info = cdp.version(s.resolved_cdp_url)
        if info:
            print(f"UP   {s.resolved_cdp_url}  {info.get('Browser')}  pages={len(cdp.list_pages(s.resolved_cdp_url))}")
        else:
            print(f"DOWN {s.resolved_cdp_url}")
            return 1
    return 0


def cmd_copy_profile(args) -> int:
    from app.browser import installed

    s = Settings.from_env()
    src = Path(args.source).expanduser() if args.source else installed.default_user_data_dirs()[0]
    dst = installed.copy_profile(src, args.profile, s.chrome_user_data_dir)
    print(f"Copied to {dst}. Set CHROME_PROFILE_DIRECTORY={args.profile} in .env, then `make chrome`.")
    return 0


def cmd_doctor(args) -> int:
    from app.browser import cdp, installed
    from app.llm import PROVIDERS, resolve_api_key

    s = Settings.from_env()
    ok = True

    def line(good: bool, label: str, detail: str = "") -> None:
        nonlocal ok
        ok = ok and good
        print(f"[{'OK' if good else '!!'}] {label:<26} {detail}")

    print(f"python {sys.version.split()[0]} on {platform.system()} {platform.machine()}")
    info = PROVIDERS.get(s.llm_provider)
    line(info is not None, "LLM provider", s.llm_provider)
    if info:
        line(bool(resolve_api_key(s)) or not info.needs_key, "LLM API key",
             "set" if resolve_api_key(s) else f"missing ({' / '.join(info.key_env)})")
        line(True, "LLM model", s.llm_model or f"{info.default_model} (default)")
    try:
        line(True, "Installed Chrome (mode 1)", installed.find_chrome_binary(s.chrome_binary))
    except FileNotFoundError as e:
        line(False, "Installed Chrome (mode 1)", str(e))
    up = cdp.is_ready(s.resolved_cdp_url)
    print(f"[--] {'CDP endpoint':<26} {s.resolved_cdp_url} {'UP' if up else 'down (fine until you use mode 1)'}")
    try:
        from browser_use.browser.watchdogs.local_browser_watchdog import LocalBrowserWatchdog

        path = s.fresh_executable_path or LocalBrowserWatchdog._find_installed_browser_path()
        line(bool(path), "Browser for mode 2", path or "none - run `make install-browser`")
    except Exception as e:
        line(False, "Browser for mode 2", str(e))
    line(True, "Default mode", f"{s.browser_mode} (headless={s.headless})")
    return 0 if ok else 1


def cmd_cost(args) -> int:
    from app import cost

    s = Settings.from_env()
    cap = f" / cap ${s.max_daily_llm_cost:.2f}" if s.max_daily_llm_cost else ""
    print(f"today: ${cost.today_cost(s):.4f}{cap}   ({cost.cost_file(s)})")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="bub", description="browser-use boilerplate CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tasks", help="list tasks").set_defaults(fn=cmd_tasks)

    r = sub.add_parser("run", help="run one task")
    r.add_argument("task")
    r.add_argument("-i", "--input", action="append", default=[], help="key=value (repeatable)")
    r.add_argument("-m", "--mode", choices=["installed", "fresh"], default=None)
    hg = r.add_mutually_exclusive_group()
    hg.add_argument("--headless", dest="headless", action="store_true", default=None)
    hg.add_argument("--headed", dest="headless", action="store_false")
    r.add_argument("--json", action="store_true", help="print the full result as JSON")
    r.set_defaults(fn=cmd_run)

    c = sub.add_parser("chrome", help="mode 1: installed Chrome with a CDP port")
    c.add_argument("action", choices=["start", "stop", "status"])
    c.add_argument("--headless", action="store_true", default=None)
    c.set_defaults(fn=cmd_chrome)

    cp = sub.add_parser("copy-profile", help="copy an everyday Chrome profile for mode 1")
    cp.add_argument("--source", default="", help="Chrome user data dir (default: this OS's Chrome dir)")
    cp.add_argument("--profile", default="Default", help='profile folder, e.g. "Default" or "Profile 1"')
    cp.set_defaults(fn=cmd_copy_profile)

    sub.add_parser("doctor", help="check the setup").set_defaults(fn=cmd_doctor)
    sub.add_parser("cost", help="today's LLM spend").set_defaults(fn=cmd_cost)

    args = p.parse_args(argv)
    _setup_logging(Settings.from_env().log_level)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130
    except (ValueError, KeyError, FileNotFoundError, ConnectionError, RuntimeError, TimeoutError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
