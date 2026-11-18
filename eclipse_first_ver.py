#!/usr/bin/env python3
"""
Eclipse Terminal
Command registry + auto help() for the Eclipse OS.
"""

import os
import sys
import platform
import time
import shutil

# ============================================================
#  STATE
# ============================================================
STATE = {
    "cwd": os.getcwd(),
    "user": "eclipse",
    "host": "eclipse",
}

# The command registry: name -> {"fn": function, "desc": description}
COMMANDS = {}


def register(name, desc=""):
    """Decorator to register a command."""
    def wrapper(fn):
        COMMANDS[name] = {"fn": fn, "desc": desc or fn.__doc__ or ""}
        return fn
    return wrapper


# ============================================================
#  PROMPT + HELPERS
# ============================================================
def prompt():
    return f"{STATE['user']}@{STATE['host']}> "


def print_header(title):
    print("=" * 50)
    print(f"  {title}")
    print("=" * 50)


def resolve_path(path):
    """Resolve a path relative to the persistent cwd."""
    if not path:
        return STATE["cwd"]
    path = os.path.expanduser(path.strip().strip('"').strip("'"))
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(STATE["cwd"], path))


# ============================================================
#  CORE COMMANDS
# ============================================================
@register("help", "List all available commands.")
def cmd_help(args):
    print_header("Eclipse Terminal — Command List")
    # Sort alphabetically for a clean list
    for name in sorted(COMMANDS.keys()):
        desc = COMMANDS[name]["desc"]
        print(f"  {name:<12} {desc}")
    print()


@register("cls", "Clear the screen.")
def cmd_cls(args):
    os.system("cls" if os.name == "nt" else "clear")


@register("exit", "Exit Eclipse Terminal.")
def cmd_exit(args):
    print("Shutting down Eclipse Terminal...")
    sys.exit(0)


# ============================================================
#  FILESYSTEM COMMANDS (Windows-flavored)
# ============================================================
@register("cd", "Change directory.  Usage: cd <path>")
def cmd_cd(args):
    if not args:
        print(STATE["cwd"])
        return
    target = resolve_path(args[0])
    if os.path.isdir(target):
        STATE["cwd"] = target
    else:
        print(f"[ERROR] Not a directory: {target}")


@register("pwd", "Print the current working directory.")
def cmd_pwd(args):
    print(STATE["cwd"])


@register("dir", "List directory contents.")
def cmd_dir(args):
    target = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(target):
        print(f"[ERROR] Not a directory: {target}")
        return
    try:
        entries = sorted(os.listdir(target))
    except PermissionError:
        print(f"[ERROR] Access denied: {target}")
        return
    if not entries:
        print("[empty]")
        return
    for e in entries:
        full = os.path.join(target, e)
        tag = "<DIR>" if os.path.isdir(full) else "     "
        print(f"  {tag}  {e}")


@register("type", "Print contents of a file.  Usage: type <file>")
def cmd_type(args):
    if not args:
        print("[ERROR] Missing file argument.")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            print(f.read())
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  SYSTEM COMMANDS
# ============================================================
@register("echo", "Print a message.  Usage: echo <text>")
def cmd_echo(args):
    print(" ".join(args))


@register("whoami", "Show the current Eclipse user.")
def cmd_whoami(args):
    print(STATE["user"])


@register("ver", "Show Eclipse OS version.")
def cmd_ver(args):
    print("Eclipse OS  [Version 0.1.0]")


@register("sysinfo", "Show basic system information.")
def cmd_sysinfo(args):
    print_header("Eclipse OS — System Info")
    print(f"  OS       : Eclipse OS 0.1.0")
    print(f"  Kernel   : eclipse-kernel 0.1.0")
    print(f"  User     : {STATE['user']}")
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {platform.python_version()}")
    print(f"  cwd      : {STATE['cwd']}")
    print()


@register("time", "Show current system time.")
def cmd_time(args):
    print(time.strftime("%Y-%m-%d %H:%M:%S"))


# ============================================================
#  MAIN LOOP
# ============================================================
def dispatch(line):
    """Parse a line and run the matching command."""
    parts = line.strip().split()
    if not parts:
        return
    name = parts[0].lower().rstrip("()")   # allow 'help()' or 'help'
    args = parts[1:]
    cmd = COMMANDS.get(name)
    if not cmd:
        print(f"[ERROR] Unknown command: {name}   (type 'help' for a list)")
        return
    try:
        cmd["fn"](args)
    except Exception as e:
        print(f"[ERROR] {e}")


def banner():
    print_header("Eclipse Terminal")
    print("  Type 'help' to see available commands.")
    print()


def main():
    banner()
    while True:
        try:
            line = input(prompt())
        except (EOFError, KeyboardInterrupt):
            print()
            break
        dispatch(line)


if __name__ == "__main__":
    main()
