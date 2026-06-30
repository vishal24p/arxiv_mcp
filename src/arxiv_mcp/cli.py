"""CLI: install (write agent configs) | serve (run the MCP server).

Usage:
  arxiv-mcp install                          # auto-detect agents, write configs
  arxiv-mcp install --dry-run                # show what would change
  arxiv-mcp install --only codex             # write even if config missing
  arxiv-mcp serve                            # run the MCP server (stdio)

Each agent stores MCP server config differently:

  Claude Desktop / Claude Code / Cursor  -> JSON, key "mcpServers"
  Codex CLI                              -> TOML, table "[mcp_servers]"

Both writers surgically insert/update the "arxiv" block without
touching other settings. Originals are backed up to <path>.bak.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import tomli_w


def _candidate_paths() -> list[tuple[str, str, Path, str]]:
    """Return [(agent_id, format, path, root_table), ...].

    format  = "json" or "toml"
    root_table = the top-level key/table the server entry lives under
    """
    home = Path.home()
    out: list[tuple[str, str, Path, str]] = []

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(home / "AppData/Roaming"))
        cd = Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        cd = home / "Library/Application Support/Claude/claude_desktop_config.json"
    else:
        cd = home / ".config/Claude/claude_desktop_config.json"
    out.append(("claude-desktop", "json", cd, "mcpServers"))

    out.append(("claude-code", "json", home / ".claude.json", "mcpServers"))
    out.append(("cursor", "json", home / ".cursor" / "mcp.json", "mcpServers"))

    out.append(("codex", "toml", home / ".codex" / "config.toml", "mcp_servers"))

    return out


def _server_entry(python: str, project_dir: Path) -> dict:
    """The MCP server spec — same shape regardless of agent format."""
    return {
        "command": python,
        "args": ["-m", "arxiv_mcp"],
        "env": {"ARXIV_MCP_PAPERS_DIR": str(project_dir / "papers")},
    }


def _write_json(
    config_path: Path,
    root_key: str,
    server_name: str,
    server_entry: dict,
    *,
    dry_run: bool,
) -> bool:
    """Insert server_entry into <root_key>.<server_name>. Return True if changed."""
    original: dict = {}
    if config_path.exists():
        try:
            original = json.loads(config_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            print(f"  ! {config_path.name} is not valid JSON; skipping", file=sys.stderr)
            return False
        if not isinstance(original, dict):
            print(f"  ! {config_path.name} is not a JSON object; skipping", file=sys.stderr)
            return False

    block = original.setdefault(root_key, {})
    if not isinstance(block, dict):
        print(f"  ! {config_path.name}['{root_key}'] is not an object; skipping",
              file=sys.stderr)
        return False

    if block.get(server_name) == server_entry:
        print(f"  = {config_path} already has '{server_name}', unchanged")
        return False

    if dry_run:
        print(f"  ~ would set {config_path}['{root_key}']['{server_name}']")
        return True

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        shutil.copy2(config_path, config_path.with_suffix(config_path.suffix + ".bak"))

    block[server_name] = server_entry
    config_path.write_text(json.dumps(original, indent=2), encoding="utf-8")
    print(f"  + wrote {config_path}['{root_key}']['{server_name}']")
    return True


def _load_toml_or_empty(path: Path) -> dict:
    """Read a TOML file as dict, or return {} if missing/empty/invalid."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore

    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = tomllib.loads(text)
    except Exception as e:
        print(f"  ! {path.name} is not valid TOML ({e}); skipping", file=sys.stderr)
        return {"__invalid__": True}
    return data if isinstance(data, dict) else {}


def _write_toml(
    config_path: Path,
    root_key: str,
    server_name: str,
    server_entry: dict,
    *,
    dry_run: bool,
) -> bool:
    """Insert server_entry into [root_key.server_name] in a TOML file."""
    data = _load_toml_or_empty(config_path)
    if data.get("__invalid__"):
        return False

    block = data.setdefault(root_key, {})
    if not isinstance(block, dict):
        print(f"  ! {config_path}['{root_key}'] is not a table; skipping", file=sys.stderr)
        return False

    if block.get(server_name) == server_entry:
        print(f"  = {config_path} already has '{server_name}', unchanged")
        return False

    if dry_run:
        print(f"  ~ would set {config_path}['{root_key}']['{server_name}']")
        return True

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        shutil.copy2(config_path, config_path.with_suffix(config_path.suffix + ".bak"))

    block[server_name] = server_entry
    config_path.write_text(tomli_w.dumps(data), encoding="utf-8")
    print(f"  + wrote {config_path}['{root_key}']['{server_name}']")
    return True


def _write(
    fmt: str,
    config_path: Path,
    root_key: str,
    server_name: str,
    server_entry: dict,
    *,
    dry_run: bool,
) -> bool:
    if fmt == "json":
        return _write_json(config_path, root_key, server_name, server_entry, dry_run=dry_run)
    if fmt == "toml":
        return _write_toml(config_path, root_key, server_name, server_entry, dry_run=dry_run)
    raise ValueError(f"unknown config format: {fmt}")


def cmd_install(args: argparse.Namespace) -> int:
    """Detect installed agents and patch their MCP configs."""
    python = sys.executable
    project_dir = Path(__file__).resolve().parent.parent.parent
    server_entry = _server_entry(python, project_dir)

    candidates = _candidate_paths()
    only = getattr(args, "only", None)
    if only:
        targets = [(n, f, p, k) for (n, f, p, k) in candidates if n in only]
    else:
        targets = [(n, f, p, k) for (n, f, p, k) in candidates if p.exists()]

    if not targets:
        print("No known agent config files found on this system.")
        print("Pass --only <agent> to create one anyway. Known agents:")
        for n, _, p, _ in candidates:
            print(f"  {n:20s} {p}")
        return 1

    print(f"Detected {len(targets)} agent config(s):")
    changed = 0
    for name, fmt, path, root_key in targets:
        print(f"  * {name:20s} [{fmt}] {path}")
        if _write(fmt, path, root_key, "arxiv", server_entry, dry_run=args.dry_run):
            changed += 1

    print()
    if args.dry_run:
        print(f"Dry run: {changed} change(s) would be made.")
    else:
        print(f"Done. {changed} config file(s) updated.")
        print()
        print("Restart your agent to activate. Then ask:")
        print('  "find 3 papers on mixture of experts"')
    return 0


def cmd_serve(_args: argparse.Namespace) -> int:
    """Run the MCP server over stdio. Used as console-script entrypoint."""
    from .server import main
    main()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arxiv-mcp")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser("install", help="Write MCP configs for detected agents")
    p_install.add_argument("--dry-run", action="store_true",
                           help="Show what would change without writing")
    p_install.add_argument("--only", action="append",
                           help="Restrict to one agent (repeatable): "
                                "claude-desktop, claude-code, cursor, codex")
    p_install.set_defaults(func=cmd_install)

    p_serve = sub.add_parser("serve", help="Run the MCP server (stdio)")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
