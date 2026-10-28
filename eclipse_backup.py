#!/usr/bin/env python3
"""
Eclipse Shell v0.6.2
Copyright (c) 2026 ilikehamandcheese11. All rights reserved.

This software is proprietary. See LICENSE file for terms.
Unauthorized copying, distribution, or modification is prohibited.
"""

import os
import sys
import platform
import time
import shutil
import subprocess
import csv
import io
import hashlib
import random
import string
import datetime
import json
import zipfile
import tarfile
import tempfile
import re
import urllib.parse
import base64 as _b64
import ctypes

try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        readline = None

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ============================================================
#  STATE
# ============================================================
STATE = {
    "cwd": os.getcwd(),
    "user": "eclipse",
    "host": "eclipse",
    "history": [],
    "version": "0.6.2",
    "status": "indev",
    "author": "ilikehamandcheese11",
    "youtube": "https://www.youtube.com/@ilikehamandcheese11",
    "telegram" : "t.me/ilikehamandcheese11",
    "aliases": {},
}

COMMANDS = {}

RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
BLUE = "\033[94m"; MAGENTA = "\033[95m"; CYAN = "\033[96m"; WHITE = "\033[97m"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "build", "dist", ".cache", "System Volume Information"}


# ============================================================
#  REGISTRY
# ============================================================
def register(name, desc="", category="General", usage="", examples=None):
    def wrapper(fn):
        COMMANDS[name] = {
            "fn": fn,
            "desc": desc or fn.__doc__ or "",
            "category": category,
            "usage": usage,
            "examples": examples or [],
        }
        return fn
    return wrapper


# ============================================================
#  PLATFORM
# ============================================================
def is_windows():
    return platform.system() == "Windows"


def is_android():
    if "com.termux" in os.environ.get("PREFIX", ""):
        return True
    if "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
        return True
    return False


def console_encoding():
    if not is_windows():
        return "utf-8"
    try:
        return f"cp{ctypes.windll.kernel32.GetConsoleOutputCP()}"
    except Exception:
        return "cp1252"


# ============================================================
#  HELPERS
# ============================================================
def prompt():
    return f"{STATE['user']}@{STATE['host']}> "


def print_header(title):
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def resolve_path(path):
    if not path:
        return STATE["cwd"]
    path = os.path.expanduser(path.strip().strip('"').strip("'"))
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(STATE["cwd"], path))


def run_shell(cmd, live=False, timeout=30):
    try:
        if live:
            subprocess.run(cmd, shell=True)
            return ""
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding=console_encoding(), errors="replace", timeout=timeout,
        )
        out = r.stdout or ""
        if r.stderr:
            out += "\n[stderr]\n" + r.stderr
        return out if out.strip() else "[no output]"
    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out."
    except Exception as e:
        return f"[ERROR] {e}"


def _safe_run(cmd, timeout=15):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding=console_encoding(), errors="replace", timeout=timeout,
        )
        return r.stdout or ""
    except Exception:
        return ""


def human_kb(kb):
    if kb < 1024: return f"{kb} K"
    mb = kb / 1024
    if mb < 1024: return f"{mb:.1f} MB"
    return f"{mb / 1024:.2f} GB"


def human_bytes(b):
    try:
        b = float(b)
    except (TypeError, ValueError):
        return "?"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.2f} {unit}" if unit != "B" else f"{b:.0f} B"
        b /= 1024
    return f"{b:.2f} PB"


# ============================================================
#  PROCESSES
# ============================================================
def get_processes():
    if HAS_PSUTIL:
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = p.info
                mem_kb = (info["memory_info"].rss // 1024) if info["memory_info"] else 0
                procs.append({"pid": info["pid"], "name": info["name"] or "?",
                              "mem_kb": mem_kb, "user": ""})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs

    procs = []
    try:
        if is_windows():
            out = subprocess.run(
                "tasklist /FO CSV /NH", shell=True, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=20,
            ).stdout or ""
            for row in csv.reader(io.StringIO(out)):
                if len(row) >= 5:
                    try: pid_int = int(row[1])
                    except ValueError: pid_int = 0
                    try: mem_kb = int(row[4].replace(",", "").replace(" K", "").strip())
                    except ValueError: mem_kb = 0
                    procs.append({"pid": pid_int, "name": row[0], "mem_kb": mem_kb, "user": ""})
        else:
            out = subprocess.run(
                "ps -eo pid,user,comm,rss", shell=True, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=20,
            ).stdout or ""
            for line in out.strip().splitlines()[1:]:
                parts = line.split(None, 3)
                if len(parts) < 4: continue
                try:
                    procs.append({"pid": int(parts[0]), "name": parts[2],
                                  "mem_kb": int(parts[3]), "user": parts[1]})
                except ValueError: continue
    except Exception as e:
        return [{"pid": 0, "name": f"[ERROR] {e}", "mem_kb": 0, "user": ""}]
    return procs


# ============================================================
#  VRAM
# ============================================================
def _read_vram_from_registry(gpu_name):
    try:
        base = r"HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        r = _safe_run(f'reg query "{base}" /s /v HardwareInformation.qwMemorySize', timeout=15)
        current_key = None
        vram_by_key = {}
        for line in r.splitlines():
            line = line.strip()
            if line.startswith("HKEY_"): current_key = line
            elif "HardwareInformation.qwMemorySize" in line:
                parts = line.split()
                if len(parts) >= 3:
                    try: vram_by_key[current_key] = int(parts[-1], 16)
                    except ValueError: pass
        if not vram_by_key: return None
        if gpu_name:
            for key, vram in vram_by_key.items():
                r2 = _safe_run(f'reg query "{key}" /v DriverDesc', timeout=10)
                if gpu_name.lower() in r2.lower(): return vram
        return max(vram_by_key.values())
    except Exception:
        return None


# ============================================================
#  SPECS
# ============================================================
def _win_specs():
    info = {}
    r = _safe_run('wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed /format:list')
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Name="): info["cpu_name"] = line.split("=", 1)[1]
        elif line.startswith("NumberOfCores="): info["cpu_cores"] = line.split("=", 1)[1]
        elif line.startswith("NumberOfLogicalProcessors="): info["cpu_threads"] = line.split("=", 1)[1]
        elif line.startswith("MaxClockSpeed="): info["cpu_mhz"] = line.split("=", 1)[1]
    r = _safe_run('wmic computersystem get TotalPhysicalMemory /format:list')
    for line in r.splitlines():
        if line.strip().startswith("TotalPhysicalMemory="):
            try: info["ram_bytes"] = int(line.strip().split("=", 1)[1])
            except ValueError: pass
    r = _safe_run('wmic path win32_VideoController get Name /format:list')
    gpus = []
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Name=") and line.split("=", 1)[1]:
            gpus.append({"name": line.split("=", 1)[1]})
    for g in gpus:
        g["vram"] = _read_vram_from_registry(g.get("name", ""))
    if gpus: info["gpus"] = gpus
    r = _safe_run('wmic baseboard get Product,Manufacturer /format:list')
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Product=") and line.split("=", 1)[1]: info["motherboard"] = line.split("=", 1)[1]
        elif line.startswith("Manufacturer=") and line.split("=", 1)[1]: info["mobo_vendor"] = line.split("=", 1)[1]
    r = _safe_run('wmic computersystem get Manufacturer,Model /format:list')
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Manufacturer=") and line.split("=", 1)[1]: info["sys_vendor"] = line.split("=", 1)[1]
        elif line.startswith("Model=") and line.split("=", 1)[1]: info["sys_model"] = line.split("=", 1)[1]
    r = _safe_run('wmic diskdrive get Model,Size /format:list')
    cur = {}; disks = []
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Model="): cur["model"] = line.split("=", 1)[1]
        elif line.startswith("Size=") and line.split("=", 1)[1].strip():
            try: cur["size"] = int(line.split("=", 1)[1])
            except ValueError: cur["size"] = None
            if "model" in cur:
                if cur.get("size"): disks.append(f"{cur['model']} ({human_bytes(cur['size'])})")
                else: disks.append(cur["model"])
            cur = {}
    if disks: info["disks"] = disks
    return info


def _linux_specs():
    info = {}
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line and "cpu_name" not in info:
                    info["cpu_name"] = line.split(":", 1)[1].strip()
    except Exception: pass
    info["cpu_threads"] = str(os.cpu_count() or "?")
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    info["ram_bytes"] = int(line.split()[1]) * 1024
                    break
    except Exception: pass
    if is_android():
        info["sys_model"] = _safe_run("getprop ro.product.model", timeout=5).strip()
        info["sys_vendor"] = _safe_run("getprop ro.product.manufacturer", timeout=5).strip()
    return info


def _mac_specs():
    info = {}
    r = _safe_run("system_profiler SPHardwareDataType", timeout=20)
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Chip:") or line.startswith("Processor Name:"):
            info["cpu_name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Total Number of Cores:"):
            info["cpu_threads"] = line.split(":", 1)[1].strip()
        elif line.startswith("Memory:"): info["ram_str"] = line.split(":", 1)[1].strip()
        elif line.startswith("Model Name:"): info["sys_model"] = line.split(":", 1)[1].strip()
    return info


def collect_specs():
    if is_windows(): return _win_specs()
    if platform.system() == "Darwin": return _mac_specs()
    return _linux_specs()


# ============================================================
#  PROGRAM FINDER
# ============================================================
def _win_search_roots():
    roots = []
    user = os.environ.get("USERPROFILE", "")
    if user:
        roots += [os.path.join(user, "AppData", "Local"),
                  os.path.join(user, "AppData", "Roaming"),
                  os.path.join(user, "Desktop"),
                  os.path.join(user, "Downloads")]
    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        p = os.environ.get(env)
        if p: roots.append(p)
    return [r for r in roots if os.path.isdir(r)]


_PROGRAM_CACHE = {"list": None, "roots_key": None}


def _build_program_index():
    roots = _win_search_roots() if is_windows() else ["/usr/bin", "/usr/local/bin", "/opt"]
    ext = ".exe" if is_windows() else ""
    key = "|".join(roots) + "|" + ext
    if _PROGRAM_CACHE["list"] is not None and _PROGRAM_CACHE["roots_key"] == key:
        return _PROGRAM_CACHE["list"]
    found = []
    for root in roots:
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            if dirpath.count(os.sep) - base_depth > 4:
                dirnames[:] = []
                continue
            for f in filenames:
                if ext and f.lower().endswith(ext):
                    found.append(os.path.join(dirpath, f))
    _PROGRAM_CACHE["list"] = found
    _PROGRAM_CACHE["roots_key"] = key
    return found


def find_program(name):
    if os.path.isabs(name) and os.path.exists(name): return name
    local = os.path.join(STATE["cwd"], name)
    if os.path.exists(local): return local
    found = shutil.which(name)
    if found: return found
    print(f"[search] scanning for '{name}'...")
    index = _build_program_index()
    q = name.lower().replace(".exe", "").strip()
    scored = []
    for path in index:
        t = os.path.basename(path).lower().replace(".exe", "").strip()
        if q == t: scored.append((1000, path))
        elif t.startswith(q): scored.append((800 - len(t), path))
        elif q in t: scored.append((600 - len(t), path))
    if not scored: return None
    scored.sort(reverse=True)
    return scored[0][1]


# ============================================================
#  LICENSE
# ============================================================
LICENSE_TEXT = """Eclipse Shell — Proprietary License
Copyright (c) 2026 ilikehamandcheese11. All rights reserved.

================================================================
                         TERMS OF USE
================================================================

1. OWNERSHIP
   Eclipse Shell (the "Software"), including its source code,
   documentation, branding, name, and all associated assets, is
   the exclusive property of ilikehamandcheese11 (the "Author").
   All rights not expressly granted in this License are reserved
   by the Author.

2. GRANT OF LICENSE
   You are granted a limited, non-exclusive, non-transferable,
   revocable license to:
     a) Download and use the Software for personal, educational,
        or internal business purposes.
     b) Make a single backup copy of the Software for archival
        purposes only, provided it retains this License.

3. RESTRICTIONS
   You may NOT, under any circumstances:
     a) Copy, redistribute, publish, upload, share, or otherwise
        make the Software available to any third party.
     b) Sell, resell, sublicense, rent, lease, or commercialize.
     c) Modify, adapt, translate, reverse-engineer, decompile,
        disassemble, or create derivative works.
     d) Remove, alter, or obscure any copyright notice.
     e) Claim authorship, ownership, or credit for the Software.
     f) Rebrand, rename, or present the Software under a
        different name or identity.
     g) Use the Software as part of a larger product offered
        for sale without explicit written permission.
     h) Use the Software for any unlawful purpose.

4. THIRD-PARTY COMPONENTS
   The Software may reference or invoke third-party programs,
   libraries, or services. Use of those components is governed
   by their own respective licenses.

5. NO WARRANTY
   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
   KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
   WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
   PURPOSE, AND NON-INFRINGEMENT.

6. LIMITATION OF LIABILITY
   IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM,
   DAMAGES, OR OTHER LIABILITY ARISING FROM, OUT OF, OR IN
   CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
   IN THE SOFTWARE.

7. USER RESPONSIBILITY
   You are solely responsible for the commands you run, and you
   will comply with all applicable laws while using the Software.

8. TERMINATION
   This License terminates automatically if you breach any term.

9. ENFORCEMENT
   Unauthorized use constitutes copyright infringement.

10. CONTACT
    Author  : ilikehamandcheese11
    YouTube : https://www.youtube.com/@ilikehamandcheese11
    Telegram : t.me/ilikehamandcheese11

================================================================
   By using Eclipse Shell, you acknowledge that you have read,
   understood, and agree to be bound by the terms of this License.
================================================================
"""


# ============================================================
#  CORE COMMANDS
# ============================================================
@register("help", "Lists every command sorted into groups. Pass a category to filter down to just that one.",
          category="Shell", usage="help [category]", examples=["help", "help Filesystem"])
def cmd_help(args, stdin_text=None):
    by_cat = {}
    for name, meta in COMMANDS.items():
        by_cat.setdefault(meta["category"], []).append((name, meta["desc"]))
    only = args[0].lower() if args else None
    print_header(f"Eclipse Shell — {len(COMMANDS)} commands")
    for cat in sorted(by_cat):
        if only and only != cat.lower():
            continue
        print(f"\n  [{cat}]")
        for name, desc in sorted(by_cat[cat]):
            print(f"    {name:<14} {desc}")
    print()


@register("man", "Full documentation for one command. Shows what it does, its arguments, and example calls.",
          category="Shell", usage="man <command>", examples=["man dir", "man curl"])
def cmd_man(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: man <command>")
        return
    name = args[0].lower().rstrip("()")
    meta = COMMANDS.get(name)
    if not meta:
        print(f"[ERROR] Unknown command: {name}")
        return
    print_header(f"{name}  —  {meta['category']}")
    print(f"  {meta['desc']}")
    if meta["usage"]:
        print(f"\n  Usage: {meta['usage']}")
    if meta["examples"]:
        print("\n  Examples:")
        for ex in meta["examples"]:
            print(f"    {ex}")
    print()


@register("pkglist", "Dumps every command name onto one line per category. Fast scan of what's available.",
          category="Shell")
def cmd_pkglist(args, stdin_text=None):
    by_cat = {}
    for name, meta in COMMANDS.items():
        by_cat.setdefault(meta["category"], []).append(name)
    for cat, names in sorted(by_cat.items()):
        print(f"  {cat}: {' '.join(sorted(names))}")
    print()


@register("about", "Version, author, license, platform info, and contact links.",
          category="Shell")
def cmd_about(args, stdin_text=None):
    print_header("About Eclipse Shell")
    print(f"  Name     : Eclipse Shell")
    print(f"  Version  : {STATE['version']} ({STATE['status']})")
    print(f"  Author   : {STATE['author']}")
    print(f"  License  : Proprietary")
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {platform.python_version()}")
    print(f"  psutil   : {'yes' if HAS_PSUTIL else 'no (optional speedup)'}")
    print()
    print(f"  Contact  : {STATE['youtube']}  |  {STATE['discord']}")
    print()


@register("license", "Prints the full license text.",
          category="Shell")
def cmd_license(args, stdin_text=None):
    print(LICENSE_TEXT)


@register("cls", "Clears the terminal.",
          category="Shell")
def cmd_cls(args, stdin_text=None):
    if is_windows():
        os.system("")
    sys.stdout.write("\033[2J\033[3J\033[H")
    sys.stdout.flush()


@register("clear", "Alias of cls.",
          category="Shell")
def cmd_clear(args, stdin_text=None):
    cmd_cls(args)


@register("exit", "Exits the shell.",
          category="Shell")
def cmd_exit(args, stdin_text=None):
    print("Shutting down Eclipse Shell...")
    raise SystemExit(0)


@register("quit", "Alias of exit.",
          category="Shell")
def cmd_quit(args, stdin_text=None):
    cmd_exit(args)


@register("history", "Numbered list of commands you've run this session.",
          category="Shell")
def cmd_history(args, stdin_text=None):
    if not STATE["history"]:
        print("[empty]")
        return
    for i, h in enumerate(STATE["history"], 1):
        print(f"  {i:>4}  {h}")


@register("clrhist", "Wipes the command history.",
          category="Shell")
def cmd_clrhist(args, stdin_text=None):
    STATE["history"].clear()
    print("[ok] History cleared")


@register("last", "Prints the last command you ran.",
          category="Shell")
def cmd_last(args, stdin_text=None):
    print(f"  {STATE['history'][-1]}" if STATE["history"] else "[empty]")


@register("version", "Prints the version string.",
          category="Shell")
def cmd_version(args, stdin_text=None):
    print(f"Eclipse Shell [Version {STATE['version']} {STATE['status']}]")


@register("ver", "Alias of version.",
          category="Shell")
def cmd_ver(args, stdin_text=None):
    cmd_version(args)


@register("commands", "Count of loaded commands.",
          category="Shell")
def cmd_commands(args, stdin_text=None):
    print(f"  {len(COMMANDS)} commands registered")


@register("allhelp", "Every command name in a compact grid. No descriptions, just the names.",
          category="Shell")
def cmd_allhelp(args, stdin_text=None):
    names = sorted(COMMANDS.keys())
    print(f"  {len(names)} commands:")
    for i in range(0, len(names), 5):
        print("  " + "  ".join(f"{n:<14}" for n in names[i:i + 5]))


@register("tips", "Picks a random tip from a list of shortcuts and tricks.",
          category="Shell")
def cmd_tips(args, stdin_text=None):
    tips = ["Pipes: tasklist | grep chrome", "Redirect: dir > files.txt",
            "Smart launch: start notepad", "Specs: sysinfo", "Tree: tree",
            "Search: findext py", "Banner: banner ECLIPSE",
            "History: press up arrow", "Tab-complete: type 'di' then Tab"]
    print(f"  Tip: {random.choice(tips)}")


@register("alias", "Registers a shortcut so a short word runs a longer command.",
          category="Shell", usage="alias <name>=<value>",
          examples=["alias ll=dir", "alias hi=echo hello"])
def cmd_alias(args, stdin_text=None):
    if not args:
        if not STATE["aliases"]:
            print("[no aliases]")
            return
        for k, v in STATE["aliases"].items():
            print(f"  {k} = {v}")
        return
    text = " ".join(args)
    if "=" not in text:
        print("[ERROR] Usage: alias name=command")
        return
    name, value = text.split("=", 1)
    name = name.strip()
    value = value.strip().strip('"').strip("'")
    if not name or not value:
        print("[ERROR] Missing name or value.")
        return
    STATE["aliases"][name] = value
    print(f"[alias] {name} = {value}")


@register("unalias", "Deletes a shortcut from the alias table.",
          category="Shell", usage="unalias <name>")
def cmd_unalias(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: unalias <name>")
        return
    name = args[0]
    if name in STATE["aliases"]:
        del STATE["aliases"][name]
        print(f"[alias] removed {name}")
    else:
        print(f"[ERROR] No alias: {name}")


@register("which", "Looks up where a command resolves to: a builtin, an entry on PATH, or a file in cwd.",
          category="Shell", usage="which <name>")
def cmd_which(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: which <name>")
        return
    name = args[0]
    if name in COMMANDS:
        print(f"  {name}: Eclipse Shell builtin")
        return
    found = shutil.which(name)
    if found:
        print(f"  {found}")
        return
    local = resolve_path(name)
    if os.path.exists(local):
        print(f"  {local}")
        return
    print(f"[not found] {name}")


@register("watch", "Reruns a command every N seconds with a fresh screen each time. Ctrl+C stops it.",
          category="Shell", usage="watch <secs> <cmd>")
def cmd_watch(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: watch <secs> <command>")
        return
    try:
        secs = float(args[0])
    except ValueError:
        print("[ERROR] secs must be a number.")
        return
    cmd = " ".join(args[1:])
    try:
        while True:
            os.system("cls" if is_windows() else "clear")
            print(f"[watch] every {secs}s: {cmd}")
            print("-" * 60)
            dispatch(cmd)
            time.sleep(secs)
    except KeyboardInterrupt:
        print("\n[watch] stopped")


@register("repeat", "Fires the same command N times in a row.",
          category="Shell", usage="repeat <n> <cmd>")
def cmd_repeat(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: repeat <n> <command>")
        return
    try:
        n = int(args[0])
    except ValueError:
        print("[ERROR] n must be a number.")
        return
    cmd = " ".join(args[1:])
    for i in range(n):
        print(f"--- run {i + 1}/{n} ---")
        dispatch(cmd)


@register("call", "Runs another command through the dispatcher. Pipes and redirects work.",
          category="Shell", usage="call <command> [args...]")
def cmd_call(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: call <command> [args...]")
        return
    name = args[0].lower().rstrip("()")
    if name == "call":
        print("[ERROR] 'call' cannot call itself.")
        return
    dispatch(" ".join(args))


@register("wait", "Blocks for N seconds before returning to the prompt.",
          category="Shell", usage="wait <seconds>")
def cmd_wait(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: wait <seconds>")
        return
    try:
        n = float(args[0])
        time.sleep(n)
        print(f"[ok] waited {n}s")
    except (ValueError, KeyboardInterrupt):
        print("[cancelled]")


@register("bench", "Runs a loop of math ops and scores this CPU. Higher = faster.",
          category="Shell")
def cmd_bench(args, stdin_text=None):
    print("[bench] running...")
    start = time.time()
    total = 0
    for i in range(1, 500000):
        total += i * i
    elapsed = time.time() - start
    print(f"  Time   : {elapsed:.3f}s")
    print(f"  Score  : {int(500000 / elapsed)} (higher = faster)")


@register("banner", "Renders text as big ASCII block letters.",
          category="Fun", usage="banner <text>", examples=["banner ECLIPSE"])
def cmd_banner(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: banner <text>")
        return
    text = " ".join(args).upper()
    font = {
        "A": ["  A  ", " A A ", "AAAAA", "A   A", "A   A"],
        "B": ["BBBB ", "B   B", "BBBB ", "B   B", "BBBB "],
        "C": [" CCCC", "C    ", "C    ", "C    ", " CCCC"],
        "D": ["DDDD ", "D   D", "D   D", "D   D", "DDDD "],
        "E": ["EEEEE", "E    ", "EEE  ", "E    ", "EEEEE"],
        "F": ["FFFFF", "F    ", "FFF  ", "F    ", "F    "],
        "G": [" GGGG", "G    ", "G  GG", "G   G", " GGG "],
        "H": ["H   H", "H   H", "HHHHH", "H   H", "H   H"],
        "I": ["IIIII", "  I  ", "  I  ", "  I  ", "IIIII"],
        "J": ["    J", "    J", "    J", "J   J", " JJJ "],
        "K": ["K   K", "K  K ", "KKK  ", "K  K ", "K   K"],
        "L": ["L    ", "L    ", "L    ", "L    ", "LLLLL"],
        "M": ["M   M", "MM MM", "M M M", "M   M", "M   M"],
        "N": ["N   N", "NN  N", "N N N", "N  NN", "N   N"],
        "O": [" OOO ", "O   O", "O   O", "O   O", " OOO "],
        "P": ["PPPP ", "P   P", "PPPP ", "P    ", "P    "],
        "Q": [" QQQ ", "Q   Q", "Q   Q", "Q  Q ", " QQ Q"],
        "R": ["RRRR ", "R   R", "RRRR ", "R R  ", "R  RR"],
        "S": [" SSSS", "S    ", " SSS ", "    S", "SSSS "],
        "T": ["TTTTT", "  T  ", "  T  ", "  T  ", "  T  "],
        "U": ["U   U", "U   U", "U   U", "U   U", " UUU "],
        "V": ["V   V", "V   V", "V   V", " V V ", "  V  "],
        "W": ["W   W", "W   W", "W W W", "WW WW", "W   W"],
        "X": ["X   X", " X X ", "  X  ", " X X ", "X   X"],
        "Y": ["Y   Y", " Y Y ", "  Y  ", "  Y  ", "  Y  "],
        "Z": ["ZZZZZ", "   Z ", "  Z  ", " Z   ", "ZZZZZ"],
        " ": ["     ", "     ", "     ", "     ", "     "],
        "0": [" 000 ", "0   0", "0   0", "0   0", " 000 "],
        "1": ["  1  ", " 11  ", "  1  ", "  1  ", "11111"],
        "2": [" 222 ", "2   2", "   2 ", "  2  ", "22222"],
        "3": [" 333 ", "3   3", "  33 ", "3   3", " 333 "],
        "4": ["4   4", "4   4", "44444", "    4", "    4"],
        "5": ["55555", "5    ", "5555 ", "    5", "5555 "],
        "6": [" 666 ", "6    ", "6666 ", "6   6", " 666 "],
        "7": ["77777", "    7", "   7 ", "  7  ", " 7   "],
        "8": [" 888 ", "8   8", " 888 ", "8   8", " 888 "],
        "9": [" 999 ", "9   9", " 9999", "    9", " 999 "],
    }
    for row in range(5):
        line = ""
        for ch in text:
            line += font.get(ch, ["?????"] * 5)[row] + " "
        print(line)


@register("epoch", "Converts a Unix timestamp to a readable date, or a YYYY-MM-DD date to a Unix timestamp.",
          category="Utility", usage="epoch [timestamp]")
def cmd_epoch(args, stdin_text=None):
    if not args:
        print(f"  now: {int(time.time())}")
        return
    try:
        ts = int(args[0])
        print(f"  {ts} -> {datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}")
    except ValueError:
        try:
            dt = datetime.datetime.strptime(args[0], "%Y-%m-%d")
            print(f"  {args[0]} -> {int(dt.timestamp())}")
        except Exception as e:
            print(f"[ERROR] {e}")


@register("uuid7", "Generates a time-ordered UUID, sortable by creation time.",
          category="Utility")
def cmd_uuid7(args, stdin_text=None):
    import uuid as _u
    ts = int(time.time() * 1000)
    rand = _u.uuid4().hex[8:]
    print(f"  {ts:012x}-{rand[:4]}-{rand[4:8]}-{rand[8:12]}-{rand[12:24]}")


@register("url", "URL-encodes text, or decodes it back with -d.",
          category="Utility", usage="url [-d] <text>")
def cmd_url(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: url [-d] <text>")
        return
    decode = args[0] == "-d"
    text = " ".join(args[1:] if decode else args)
    try:
        print(f"  {urllib.parse.unquote(text) if decode else urllib.parse.quote(text)}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("jwt", "Splits a JWT into its header and payload as pretty-printed JSON. Doesn't verify the signature.",
          category="Dev", usage="jwt <token>")
def cmd_jwt(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: jwt <token>")
        return
    try:
        parts = args[0].split(".")
        if len(parts) < 2:
            print("[ERROR] Not a JWT.")
            return
        def b64pad(s):
            return s + "=" * (-len(s) % 4)
        header = json.loads(_b64.urlsafe_b64decode(b64pad(parts[0])))
        payload = json.loads(_b64.urlsafe_b64decode(b64pad(parts[1])))
        print("  Header:")
        print("    " + json.dumps(header, indent=2).replace("\n", "\n    "))
        print("  Payload:")
        print("    " + json.dumps(payload, indent=2).replace("\n", "\n    "))
    except Exception as e:
        print(f"[ERROR] {e}")


@register("regex", "Runs a regex against some text and prints the match and captured groups.",
          category="Dev", usage="regex <pattern> <text>", examples=["regex \\d+ abc123def"])
def cmd_regex(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: regex <pattern> <text>")
        return
    try:
        m = re.search(args[0], " ".join(args[1:]))
        if m:
            print(f"  match: '{m.group()}'")
            for i, g in enumerate(m.groups(), 1):
                print(f"  group {i}: {g}")
        else:
            print("  no match")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("sed", "Regex find-and-replace inside a file. Writes the result back to the same file.",
          category="Text", usage="sed <file> <pattern> <replacement>")
def cmd_sed(args, stdin_text=None):
    if len(args) < 3:
        print("[ERROR] Usage: sed <file> <pattern> <replacement>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        new_data, count = re.subn(args[1], args[2], data)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_data)
        print(f"[ok] replaced {count} occurrence(s)")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("wc-lines", "Walks a directory and counts lines in every source file, then totals them.",
          category="Text", usage="wc-lines [path]")
def cmd_wc_lines(args, stdin_text=None):
    target = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(target):
        print(f"[ERROR] Not a directory: {target}")
        return
    total = 0
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith((".py", ".txt", ".md", ".js", ".ts", ".c", ".cpp", ".h")):
                continue
            full = os.path.join(root, f)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    n = sum(1 for _ in fh)
                total += n
                print(f"  {n:>6}  {full}")
            except Exception:
                pass
    print(f"\n  Total: {total} lines")


@register("du", "Recursively totals up disk usage for a directory.",
          category="Filesystem", usage="du [path]")
def cmd_du(args, stdin_text=None):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.exists(path):
        print(f"[ERROR] Not found: {path}")
        return
    if os.path.isfile(path):
        print(f"{human_bytes(os.path.getsize(path))}  {path}")
        return
    total = 0; count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
                count += 1
            except Exception:
                pass
    print(f"{human_bytes(total)}  {count} files  {path}")


@register("fileinfo", "Reads a file's magic bytes to identify its real type regardless of extension.",
          category="Dev", usage="fileinfo <file>")
def cmd_fileinfo(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: fileinfo <file>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "rb") as f:
            head = f.read(16)
        sigs = {
            b"\x89PNG": "PNG image", b"\xff\xd8\xff": "JPEG image",
            b"GIF8": "GIF image", b"PK\x03\x04": "ZIP archive",
            b"%PDF": "PDF document", b"MZ": "Windows executable",
            b"\x7fELF": "Linux executable", b"ID3": "MP3 audio",
            b"OggS": "OGG media", b"RIFF": "RIFF media",
        }
        kind = "unknown"
        for sig, name in sigs.items():
            if head.startswith(sig):
                kind = name
                break
        print(f"  Path  : {path}")
        print(f"  Type  : {kind}")
        print(f"  Size  : {human_bytes(os.path.getsize(path))}")
        print(f"  Magic : {head[:8].hex()}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("netcheck", "Runs a DNS lookup and then a short ping against a host.",
          category="Network", usage="netcheck <host>")
def cmd_netcheck(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: netcheck <host>")
        return
    host = args[0]
    print(f"[netcheck] {host}")
    print("-" * 60)
    print("[DNS]")
    print(_safe_run(f"nslookup {host}", timeout=10) or "[no output]")
    print("[PING]")
    flag = "-n" if is_windows() else "-c"
    print(_safe_run(f"ping {flag} 2 {host}", timeout=15) or "[no output]")


# ============================================================
#  FILESYSTEM
# ============================================================
@register("cd", "Switches the working directory. All relative paths after this resolve from here.",
          category="Filesystem", usage="cd [path]",
          examples=["cd ..", "cd C:\\Users", "cd Desktop"])
def cmd_cd(args, stdin_text=None):
    if not args:
        print(STATE["cwd"])
        return
    t = resolve_path(args[0])
    if os.path.isdir(t):
        STATE["cwd"] = t
    else:
        print(f"[ERROR] Not a directory: {t}")


@register("pwd", "Prints the absolute path of the current working directory.",
          category="Filesystem")
def cmd_pwd(args, stdin_text=None):
    print(STATE["cwd"])


@register("pwdshort", "Prints just the name of the current directory, no path.",
          category="Filesystem")
def cmd_pwdshort(args, stdin_text=None):
    print(os.path.basename(STATE["cwd"]) or STATE["cwd"])


@register("dir", "Lists a directory. Subfolders are tagged <DIR>.",
          category="Filesystem", usage="dir [path]")
def cmd_dir(args, stdin_text=None):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(t):
        print(f"[ERROR] Not a dir: {t}")
        return
    try:
        entries = sorted(os.listdir(t))
    except PermissionError:
        print(f"[ERROR] Access denied.")
        return
    if not entries:
        print("[empty]")
        return
    for e in entries:
        tag = "<DIR>" if os.path.isdir(os.path.join(t, e)) else "     "
        print(f"  {tag}  {e}")


@register("ls", "Unix-style directory listing. Subfolders get a trailing slash.",
          category="Filesystem", usage="ls [path]")
def cmd_ls(args, stdin_text=None):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(t):
        print(f"[ERROR] Not a dir: {t}")
        return
    for e in sorted(os.listdir(t)):
        print(e + ("/" if os.path.isdir(os.path.join(t, e)) else ""))


@register("lsd", "Lists only subdirectories, skipping files.",
          category="Filesystem")
def cmd_lsd(args, stdin_text=None):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(t):
        print(f"[ERROR] Not a dir: {t}")
        return
    dirs = [d for d in sorted(os.listdir(t)) if os.path.isdir(os.path.join(t, d))]
    for d in dirs:
        print(d + "/")
    if not dirs:
        print("[no directories]")


@register("lsf", "Lists only files, with their sizes next to them.",
          category="Filesystem")
def cmd_lsf(args, stdin_text=None):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(t):
        print(f"[ERROR] Not a dir: {t}")
        return
    files = [f for f in sorted(os.listdir(t)) if os.path.isfile(os.path.join(t, f))]
    for f in files:
        print(f"  {human_bytes(os.path.getsize(os.path.join(t, f))):>10}  {f}")
    if not files:
        print("[no files]")


@register("countfiles", "Counts total files and subdirectories under a path.",
          category="Filesystem")
def cmd_countfiles(args, stdin_text=None):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    nf = nd = 0
    for root, dirs, files in os.walk(t):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        nf += len(files)
        nd += len(dirs)
    print(f"  Files: {nf}\n  Dirs : {nd}")


@register("makedirs", "Creates several directories in one call.",
          category="Filesystem", usage="makedirs <d1> <d2>...")
def cmd_makedirs(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: makedirs <d1> <d2>...")
        return
    for d in args:
        try:
            os.makedirs(resolve_path(d), exist_ok=True)
            print(f"  [ok] {d}")
        except Exception as e:
            print(f"  [ERROR] {d}: {e}")


@register("type", "Prints a file's contents to stdout.",
          category="Filesystem", usage="type <file>")
def cmd_type(args, stdin_text=None):
    if not args:
        print("[ERROR] Missing file.")
        return
    p = resolve_path(args[0])
    if not os.path.isfile(p):
        print(f"[ERROR] File not found: {p}")
        return
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            print(f.read())
    except Exception as e:
        print(f"[ERROR] {e}")


@register("cat", "Alias of type.",
          category="Filesystem", usage="cat <file>")
def cmd_cat(args, stdin_text=None):
    cmd_type(args)


@register("mkdir", "Creates a single directory. No error if it already exists.",
          category="Filesystem", usage="mkdir <name>")
def cmd_mkdir(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: mkdir <name>")
        return
    try:
        os.makedirs(resolve_path(args[0]), exist_ok=True)
        print(f"[ok] Created {resolve_path(args[0])}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("rm", "Deletes a file. Refuses directories; use rmdir for those.",
          category="Filesystem", usage="rm <file>")
def cmd_rm(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: rm <file>")
        return
    p = resolve_path(args[0])
    if not os.path.exists(p):
        print(f"[ERROR] Not found: {p}")
        return
    try:
        if os.path.isdir(p):
            print("[ERROR] Use rmdir.")
            return
        os.remove(p)
        print(f"[ok] Removed {p}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("rmdir", "Removes an empty directory.",
          category="Filesystem", usage="rmdir <dir>")
def cmd_rmdir(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: rmdir <dir>")
        return
    try:
        os.rmdir(resolve_path(args[0]))
        print(f"[ok] Removed {resolve_path(args[0])}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("find", "Recursively searches the current directory for names containing a given string.",
          category="Filesystem", usage="find <name>")
def cmd_find(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: find <name>")
        return
    needle = args[0].lower()
    hits = 0
    for root, dirs, files in os.walk(STATE["cwd"]):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files + dirs:
            if needle in f.lower():
                print(os.path.join(root, f))
                hits += 1
                if hits >= 200:
                    print("[...truncated]")
                    return
    if hits == 0:
        print("[no matches]")


@register("head", "Prints the first N lines of a file or stdin. Default 10.",
          category="Text", usage="head <file> [n]")
def cmd_head(args, stdin_text=None):
    n = 10
    if args and len(args) > 1 and args[1].isdigit():
        n = int(args[1])
    if args:
        try:
            with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= n:
                        break
                    print(line.rstrip())
            return
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    if stdin_text is not None:
        for i, line in enumerate(stdin_text.splitlines()):
            if i >= n:
                break
            print(line)
        return
    print("[ERROR] Usage: head <file> [n]")


@register("tail", "Prints the last N lines of a file or stdin. Default 10.",
          category="Text", usage="tail <file> [n]")
def cmd_tail(args, stdin_text=None):
    n = 10
    if args and len(args) > 1 and args[1].isdigit():
        n = int(args[1])
    if args:
        try:
            with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            for line in lines[-n:]:
                print(line.rstrip())
            return
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    if stdin_text is not None:
        for line in stdin_text.splitlines()[-n:]:
            print(line)
        return
    print("[ERROR] Usage: tail <file> [n]")


@register("wc", "Prints line, word, and character counts for a file or stdin.",
          category="Text", usage="wc [file]")
def cmd_wc(args, stdin_text=None):
    if args:
        p = resolve_path(args[0])
        if not os.path.isfile(p):
            print(f"[ERROR] File not found: {p}")
            return
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                data = f.read()
        except Exception as e:
            print(f"[ERROR] {e}")
            return
        print(f"  {data.count(chr(10))}  {len(data.split())}  {len(data)}  {p}")
        return
    if stdin_text is not None:
        print(f"  {stdin_text.count(chr(10))}  {len(stdin_text.split())}  {len(stdin_text)}")
        return
    print("[ERROR] No input.")


@register("df", "Reports free and used space per drive.",
          category="System")
def cmd_df(args, stdin_text=None):
    print(run_shell("wmic logicaldisk get size,freespace,caption" if is_windows() else "df -h"))


@register("cp", "Copies a file or a directory tree to a new location.",
          category="Filesystem", usage="cp <src> <dst>")
def cmd_cp(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: cp <src> <dst>")
        return
    src = resolve_path(args[0]); dst = resolve_path(args[1])
    if not os.path.exists(src):
        print(f"[ERROR] Not found: {src}")
        return
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"[ok] Copied")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("mv", "Moves or renames a file or directory.",
          category="Filesystem", usage="mv <src> <dst>")
def cmd_mv(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: mv <src> <dst>")
        return
    src = resolve_path(args[0]); dst = resolve_path(args[1])
    if not os.path.exists(src):
        print(f"[ERROR] Not found: {src}")
        return
    try:
        shutil.move(src, dst)
        print(f"[ok] Moved")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("touch", "Creates an empty file, or bumps an existing file's mtime to now.",
          category="Filesystem", usage="touch <file>")
def cmd_touch(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: touch <file>")
        return
    try:
        with open(resolve_path(args[0]), "a", encoding="utf-8"):
            pass
        print(f"[ok] Touched")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("write", "Overwrites a file with the text you provide.",
          category="Filesystem", usage="write <file> <text...>")
def cmd_write(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: write <file> <text...>")
        return
    try:
        with open(resolve_path(args[0]), "w", encoding="utf-8") as f:
            f.write(" ".join(args[1:]) + "\n")
        print("[ok] Wrote")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("append", "Appends text to a file without touching what's already in it.",
          category="Filesystem", usage="append <file> <text...>")
def cmd_append(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: append <file> <text...>")
        return
    try:
        with open(resolve_path(args[0]), "a", encoding="utf-8") as f:
            f.write(" ".join(args[1:]) + "\n")
        print("[ok] Appended")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("rename", "Alias of mv.",
          category="Filesystem", usage="rename <src> <dst>")
def cmd_rename(args, stdin_text=None):
    cmd_mv(args)


@register("tree", "Draws the directory structure as an indented tree.",
          category="Filesystem", usage="tree [path] [depth]")
def cmd_tree(args, stdin_text=None):
    root = resolve_path(args[0]) if args else STATE["cwd"]
    max_depth = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
    if not os.path.isdir(root):
        print(f"[ERROR] Not a dir: {root}")
        return
    def walk(path, prefix, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return
        entries = [e for e in entries if e not in SKIP_DIRS]
        for i, e in enumerate(entries):
            full = os.path.join(path, e)
            is_last = (i == len(entries) - 1)
            conn = "└── " if is_last else "├── "
            print(f"{prefix}{conn}{e}")
            if os.path.isdir(full):
                ext = "    " if is_last else "│   "
                walk(full, prefix + ext, depth + 1)
    print(root)
    walk(root, "", 1)


@register("size", "Reports the total size of a file or directory on disk.",
          category="Filesystem", usage="size <path>")
def cmd_size(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: size <path>")
        return
    p = resolve_path(args[0])
    if not os.path.exists(p):
        print(f"[ERROR] Not found")
        return
    if os.path.isfile(p):
        print(f"{human_bytes(os.path.getsize(p))}  {p}")
        return
    total = 0; count = 0
    for root, dirs, files in os.walk(p):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
                count += 1
            except Exception:
                pass
    print(f"{human_bytes(total)}  {count} files  {p}")


# ============================================================
#  TEXT
# ============================================================
@register("grep", "Greps a pattern in a file, or in piped stdin. Prints matching lines with line numbers.",
          category="Text", usage="grep <pattern> [file]",
          examples=["grep foo file.txt", "dir | grep py"])
def cmd_grep(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: grep <pattern> [file]")
        return
    pat = args[0]
    if len(args) >= 2:
        p = resolve_path(args[1])
        if not os.path.isfile(p):
            print(f"[ERROR] File not found: {p}")
            return
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if pat in line:
                        print(f"{i}: {line.rstrip()}")
        except Exception as e:
            print(f"[ERROR] {e}")
        return
    if stdin_text is not None:
        for line in stdin_text.splitlines():
            if pat in line:
                print(line)
        return
    print("[ERROR] No input (need file or pipe).")


@register("sort", "Sorts lines alphabetically from a file or stdin.",
          category="Text", usage="sort [file]")
def cmd_sort(args, stdin_text=None):
    if args:
        try:
            with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    elif stdin_text is not None:
        lines = stdin_text.splitlines(keepends=True)
    else:
        print("[ERROR] No input.")
        return
    for line in sorted(lines):
        print(line.rstrip())


@register("uniq", "Drops duplicate lines, keeping only the first occurrence.",
          category="Text", usage="uniq [file]")
def cmd_uniq(args, stdin_text=None):
    if args:
        try:
            with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    elif stdin_text is not None:
        lines = stdin_text.splitlines(keepends=True)
    else:
        print("[ERROR] No input.")
        return
    seen = set()
    for line in lines:
        if line not in seen:
            seen.add(line)
            print(line.rstrip())


@register("rev", "Reverses each line character by character.",
          category="Text", usage="rev [file]")
def cmd_rev(args, stdin_text=None):
    if args:
        try:
            with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    elif stdin_text is not None:
        lines = stdin_text.splitlines()
    else:
        print("[ERROR] No input.")
        return
    for line in lines:
        print(line.rstrip()[::-1])


@register("replace", "Swaps one string for another inside a file. Saves it in place.",
          category="Text", usage="replace <file> <old> <new>")
def cmd_replace(args, stdin_text=None):
    if len(args) < 3:
        print("[ERROR] Usage: replace <file> <old> <new>")
        return
    p = resolve_path(args[0])
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        count = data.count(args[1])
        data = data.replace(args[1], args[2])
        with open(p, "w", encoding="utf-8") as f:
            f.write(data)
        print(f"[ok] Replaced {count}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("lines", "Line count for a file or stdin.",
          category="Text", usage="lines [file]")
def cmd_lines(args, stdin_text=None):
    if args:
        try:
            with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
                print(f"  {sum(1 for _ in f)} lines")
            return
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    if stdin_text is not None:
        print(f"  {len(stdin_text.splitlines())} lines")
        return
    print("[ERROR] No input.")


@register("join", "Joins all lines of a file with a separator you pick.",
          category="Text", usage="join <file> <sep>")
def cmd_join(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: join <file> <sep>")
        return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            print(args[1].join(l.rstrip("\n") for l in f))
    except Exception as e:
        print(f"[ERROR] {e}")


@register("split", "Cuts a file into smaller files of N lines each.",
          category="Text", usage="split <file> <n>")
def cmd_split(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: split <file> <n>")
        return
    p = resolve_path(args[0])
    try:
        n = int(args[1])
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        base, ext = os.path.splitext(p)
        for i in range(0, len(lines), n):
            out = f"{base}_part{i // n + 1}{ext}"
            with open(out, "w", encoding="utf-8") as f:
                f.writelines(lines[i:i + n])
            print(f"  [ok] {out}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("upper", "Converts a file or stdin to uppercase.",
          category="Text", usage="upper [file]")
def cmd_upper(args, stdin_text=None):
    if args:
        try:
            with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
                print(f.read().upper())
            return
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    if stdin_text is not None:
        print(stdin_text.upper())
        return
    print("[ERROR] No input.")


@register("lower", "Converts a file or stdin to lowercase.",
          category="Text", usage="lower [file]")
def cmd_lower(args, stdin_text=None):
    if args:
        try:
            with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
                print(f.read().lower())
            return
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    if stdin_text is not None:
        print(stdin_text.lower())
        return
    print("[ERROR] No input.")


@register("swap", "Exchanges the contents of two files.",
          category="Text", usage="swap <f1> <f2>")
def cmd_swap(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: swap <f1> <f2>")
        return
    a = resolve_path(args[0]); b = resolve_path(args[1])
    if not os.path.isfile(a) or not os.path.isfile(b):
        print("[ERROR] Both must exist.")
        return
    tmp = a + ".swaptmp"
    try:
        os.rename(a, tmp); os.rename(b, a); os.rename(tmp, b)
        print("[ok] Swapped")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("diff", "Compares two files line by line, showing which lines differ.",
          category="Text", usage="diff <f1> <f2>")
def cmd_diff(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: diff <f1> <f2>")
        return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as a:
            l1 = a.readlines()
        with open(resolve_path(args[1]), "r", encoding="utf-8", errors="replace") as b:
            l2 = b.readlines()
        diffs = 0
        for i in range(max(len(l1), len(l2))):
            x = l1[i].rstrip("\n") if i < len(l1) else ""
            y = l2[i].rstrip("\n") if i < len(l2) else ""
            if x != y:
                print(f"  {i + 1}:")
                print(f"    {RED}- {x}{RESET}")
                print(f"    {GREEN}+ {y}{RESET}")
                diffs += 1
        print(f"\n  {diffs} differing line(s)")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  ARCHIVE / CLIPBOARD
# ============================================================
@register("zip", "Bundles a file or folder into a .zip archive.",
          category="Archive", usage="zip <src> [out.zip]")
def cmd_zip(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: zip <src> [out.zip]")
        return
    src = resolve_path(args[0])
    if not os.path.exists(src):
        print(f"[ERROR] Not found")
        return
    out = resolve_path(args[1]) if len(args) > 1 else os.path.join(
        STATE["cwd"], os.path.basename(src.rstrip("/\\")) + ".zip")
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(src):
                zf.write(src, os.path.basename(src))
            else:
                for root, dirs, files in os.walk(src):
                    for f in files:
                        full = os.path.join(root, f)
                        zf.write(full, os.path.relpath(full, os.path.dirname(src)))
        print(f"[ok] Zipped -> {out}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("unzip", "Extracts a .zip archive into a directory.",
          category="Archive", usage="unzip <file.zip> [dest]")
def cmd_unzip(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: unzip <file.zip> [dest]")
        return
    src = resolve_path(args[0])
    dest = resolve_path(args[1]) if len(args) > 1 else os.path.splitext(src)[0]
    try:
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(dest)
        print(f"[ok] Extracted -> {dest}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("tar", "Bundles a file or folder into a .tar.gz archive.",
          category="Archive", usage="tar <src> [out.tar.gz]")
def cmd_tar(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: tar <src> [out.tar.gz]")
        return
    src = resolve_path(args[0])
    out = resolve_path(args[1]) if len(args) > 1 else os.path.join(
        STATE["cwd"], os.path.basename(src.rstrip("/\\")) + ".tar.gz")
    try:
        with tarfile.open(out, "w:gz") as tf:
            tf.add(src, arcname=os.path.basename(src.rstrip("/\\")))
        print(f"[ok] Tarball -> {out}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("untar", "Extracts a .tar.gz archive.",
          category="Archive", usage="untar <file.tar.gz> [dest]")
def cmd_untar(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: untar <file.tar.gz> [dest]")
        return
    dest = resolve_path(args[1]) if len(args) > 1 else STATE["cwd"]
    try:
        with tarfile.open(resolve_path(args[0]), "r:gz") as tf:
            tf.extractall(dest)
        print(f"[ok] Extracted -> {dest}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("clip", "Pipes a file's contents into the system clipboard.",
          category="Archive", usage="clip <file>")
def cmd_clip(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: clip <file>")
        return
    p = resolve_path(args[0])
    if not os.path.isfile(p):
        print(f"[ERROR] File not found")
        return
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        if is_windows():
            subprocess.run("clip", input=data, text=True, shell=True)
        elif is_android():
            subprocess.run("termux-clipboard-set", input=data, text=True, shell=True)
        else:
            print("[ERROR] Windows/Android only.")
            return
        print(f"[ok] Copied {len(data)} chars")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("paste", "Prints whatever is on the system clipboard.",
          category="Archive")
def cmd_paste(args, stdin_text=None):
    if is_windows():
        out = _safe_run("powershell Get-Clipboard", timeout=10)
    elif is_android():
        out = _safe_run("termux-clipboard-get", timeout=10)
    else:
        print("[ERROR] Windows/Android only.")
        return
    print(out if out.strip() else "[empty clipboard]")


# ============================================================
#  SYSTEM
# ============================================================
@register("echo", "Prints the arguments back out.",
          category="System", usage="echo <text>")
def cmd_echo(args, stdin_text=None):
    print(" ".join(args))


@register("whoami", "Prints the current shell user.",
          category="System")
def cmd_whoami(args, stdin_text=None):
    print(STATE["user"])


@register("sysinfo", "Full hardware report: CPU, RAM, GPUs with VRAM, motherboard, disks.",
          category="System")
def cmd_sysinfo(args, stdin_text=None):
    specs = collect_specs()
    print_header("System Information")
    print(f"  OS         : {platform.system()} {platform.release()}")
    print(f"  Hostname   : {platform.node() or '?'}")
    print(f"  Arch       : {platform.machine() or '?'}")
    print(f"  Python     : {platform.python_version()}")
    print()
    if specs.get("sys_vendor") or specs.get("sys_model"):
        print(f"  System     : {specs.get('sys_vendor','?')} {specs.get('sys_model','')}".rstrip())
    if specs.get("motherboard"):
        mobo = specs["motherboard"]
        if specs.get("mobo_vendor"):
            mobo = f"{specs['mobo_vendor']} {mobo}"
        print(f"  Motherboard: {mobo}")
    cpu = specs.get("cpu_name", platform.processor() or "?")
    extras = []
    if specs.get("cpu_cores"): extras.append(f"{specs['cpu_cores']} cores")
    if specs.get("cpu_threads"): extras.append(f"{specs['cpu_threads']} threads")
    if specs.get("cpu_mhz"):
        try:
            extras.append(f"{float(specs['cpu_mhz']) / 1000:.2f} GHz")
        except ValueError:
            pass
    print(f"  CPU        : {cpu} ({', '.join(extras)})" if extras else f"  CPU        : {cpu}")
    if specs.get("ram_bytes"):
        print(f"  RAM        : {human_bytes(specs['ram_bytes'])}")
    if specs.get("gpus"):
        for i, g in enumerate(specs["gpus"]):
            label = "GPU" if i == 0 else "           "
            name = g.get("name", "?"); vram = g.get("vram")
            if vram and vram > 0:
                print(f"  {label}        : {name} ({human_bytes(vram)} VRAM)")
            else:
                print(f"  {label}        : {name}")
    if specs.get("disks"):
        print(f"  Disks      :")
        for d in specs["disks"]:
            print(f"               - {d}")
    print()


@register("os", "Dumps OS name, release, version, architecture, and hostname.",
          category="System")
def cmd_os(args, stdin_text=None):
    print_header("Operating System")
    print(f"  System  : {platform.system()}")
    print(f"  Release : {platform.release()}")
    print(f"  Version : {platform.version()}")
    print(f"  Arch    : {platform.machine()}")
    print(f"  Node    : {platform.node()}")
    print()


@register("cpu", "Prints raw CPU info straight from the OS.",
          category="System")
def cmd_cpu(args, stdin_text=None):
    print(run_shell("wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed /format:list"
                    if is_windows() else "cat /proc/cpuinfo | head -30"))


@register("mem", "Reports used and free RAM.",
          category="System")
def cmd_mem(args, stdin_text=None):
    print(run_shell("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /format:list"
                    if is_windows() else "free -h"))


@register("gpu", "Lists installed GPUs.",
          category="System")
def cmd_gpu(args, stdin_text=None):
    print(run_shell("wmic path win32_VideoController get Name /format:list"
                    if is_windows() else "lspci | grep -i vga"))


@register("hostname", "Prints the machine hostname, or sets what the prompt shows if given an argument.",
          category="System", usage="hostname [new]",
          examples=["hostname", "hostname myshell"])
def cmd_hostname(args, stdin_text=None):
    if args:
        STATE["host"] = args[0]
        print(f"[host] prompt -> {args[0]}")
    else:
        print(platform.node())


@register("user", "Prints the current shell user.",
          category="System")
def cmd_user(args, stdin_text=None):
    print(STATE["user"])


@register("env", "Dumps all environment variables, or looks up one by name.",
          category="System", usage="env [name]")
def cmd_env(args, stdin_text=None):
    if args:
        print(os.environ.get(args[0], f"[not set] {args[0]}"))
        return
    for k, v in sorted(os.environ.items()):
        print(f"  {k}={v}")


@register("time", "Prints the current date and time.",
          category="System")
def cmd_time(args, stdin_text=None):
    print(time.strftime("%Y-%m-%d %H:%M:%S"))


@register("date", "Prints today's date.",
          category="System")
def cmd_date(args, stdin_text=None):
    print(time.strftime("%Y-%m-%d"))


@register("uptime", "Shows how long the machine has been running since boot.",
          category="System")
def cmd_uptime(args, stdin_text=None):
    if is_windows():
        try:
            tick = ctypes.windll.kernel32.GetTickCount64()
            h = tick // (1000 * 60 * 60)
            m = (tick % (1000 * 60 * 60)) // (1000 * 60)
            print(f"  System Uptime: {h}h {m}m")
        except Exception as e:
            print(f"[ERROR] {e}")
    else:
        print(run_shell("uptime"))


@register("temp", "Reports temp directory size, or empties it with 'temp clear'.",
          category="System", usage="temp [clear]")
def cmd_temp(args, stdin_text=None):
    tmpdir = tempfile.gettempdir()
    if args and args[0].lower() == "clear":
        count = 0
        for f in os.listdir(tmpdir):
            try:
                full = os.path.join(tmpdir, f)
                if os.path.isfile(full):
                    os.remove(full); count += 1
                elif os.path.isdir(full):
                    shutil.rmtree(full, ignore_errors=True); count += 1
            except Exception:
                pass
        print(f"[ok] Cleared {count} item(s)")
        return
    files = os.listdir(tmpdir)
    total = 0
    for f in files:
        try:
            total += os.path.getsize(os.path.join(tmpdir, f))
        except Exception:
            pass
    print(f"  Temp: {tmpdir}")
    print(f"  Files: {len(files)}")
    print(f"  Size : {human_bytes(total)}")


@register("proc", "How many processes are running right now.",
          category="Process")
def cmd_proc(args, stdin_text=None):
    print(f"  Running processes: {len(get_processes())}")


@register("top5", "Alias of top, fixed at 5 entries.",
          category="Process")
def cmd_top5(args, stdin_text=None):
    cmd_top(["5"])


@register("services", "Lists Windows services with their state.",
          category="System")
def cmd_services(args, stdin_text=None):
    if not is_windows():
        print("[ERROR] Windows only.")
        return
    print(run_shell("sc query type= service state= all | findstr SERVICE_NAME"))


@register("startup", "Lists programs that launch at Windows startup.",
          category="System")
def cmd_startup(args, stdin_text=None):
    if not is_windows():
        print("[ERROR] Windows only.")
        return
    print(run_shell("wmic startup get Caption,Command"))


@register("drivers", "Dumps installed Windows kernel drivers.",
          category="System")
def cmd_drivers(args, stdin_text=None):
    if not is_windows():
        print("[ERROR] Windows only.")
        return
    print(run_shell("driverquery"))


@register("info", "Short summary: user, OS, CPU, RAM, cwd, command count.",
          category="System")
def cmd_info(args, stdin_text=None):
    specs = collect_specs()
    print_header("Quick Info")
    print(f"  User   : {STATE['user']}")
    print(f"  OS     : {platform.system()} {platform.release()}")
    print(f"  Arch   : {platform.machine()}")
    print(f"  Python : {platform.python_version()}")
    print(f"  cwd    : {STATE['cwd']}")
    print(f"  CPU    : {specs.get('cpu_name', '?')}")
    print(f"  RAM    : {human_bytes(specs['ram_bytes']) if specs.get('ram_bytes') else '?'}")
    print(f"  Cmds   : {len(COMMANDS)}")
    print()


# ============================================================
#  DEV
# ============================================================
@register("py", "Runs a Python file using the interpreter that's hosting this shell.",
          category="Dev", usage="py <file.py> [args...]")
def cmd_py(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: py <file.py> [args...]")
        return
    p = resolve_path(args[0])
    if not os.path.isfile(p):
        print(f"[ERROR] File not found: {p}")
        return
    extra = " ".join(f'"{a}"' if " " in a else a for a in args[1:])
    run_shell(f'"{sys.executable}" "{p}" {extra}', live=True, timeout=300)


@register("json", "Loads a JSON file and prints it indented.",
          category="Dev", usage="json <file>")
def cmd_json(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: json <file>")
        return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8") as f:
            print(json.dumps(json.load(f), indent=2))
    except Exception as e:
        print(f"[ERROR] {e}")


@register("hex", "Hex and ASCII dump of a file's first N bytes.",
          category="Dev", usage="hex <file> [n]")
def cmd_hex(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: hex <file> [n]")
        return
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 256
    try:
        with open(resolve_path(args[0]), "rb") as f:
            data = f.read(limit)
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            h = " ".join(f"{b:02x}" for b in chunk)
            a = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"  {i:08x}  {h:<48}  {a}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("count", "Tallies files by extension under a directory.",
          category="Filesystem", usage="count [path]")
def cmd_count(args, stdin_text=None):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    ext_count = {}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower() or "(none)"
            ext_count[ext] = ext_count.get(ext, 0) + 1
    for ext, n in sorted(ext_count.items(), key=lambda x: x[1], reverse=True)[:30]:
        print(f"  {n:>6}  {ext}")


@register("todo", "Scans source files for TODO and FIXME comments.",
          category="Filesystem", usage="todo [path]")
def cmd_todo(args, stdin_text=None):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith((".py", ".js", ".ts", ".md", ".txt")):
                continue
            full = os.path.join(root, f)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if "TODO" in line.upper() or "FIXME" in line.upper():
                            print(f"  {full}:{i}  {line.strip()[:80]}")
                            count += 1
            except Exception:
                pass
    print(f"\n  {count} match(es)")


@register("nano", "Minimal in-shell line editor. Opens a file for editing, saves on Ctrl+D.",
          category="Dev", usage="nano <file>",
          examples=["nano notes.txt"])
def cmd_nano(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: nano <file>")
        return
    p = resolve_path(args[0])
    existing = []
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                existing = f.read().splitlines()
        except Exception as e:
            print(f"[ERROR] {e}")
            return
    lines = list(existing)
    print(f"[nano] editing {p} — type lines, blank line to finish")
    print("-" * 60)
    for l in lines:
        print(f"  {l}")
    print("-" * 60)
    while True:
        try:
            new = input("  > ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not new:
            break
        lines.append(new)
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
        print(f"[ok] saved {len(lines)} lines")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("sha256sum", "SHA-256 hash of one or more files.",
          category="Dev", usage="sha256sum <file> [file...]")
def cmd_sha256sum(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: sha256sum <file> [file...]")
        return
    for f in args:
        p = resolve_path(f)
        if not os.path.isfile(p):
            print(f"[ERROR] Not found: {p}")
            continue
        try:
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            print(f"  {h.hexdigest()}  {p}")
        except Exception as e:
            print(f"[ERROR] {e}")


@register("sha1sum", "SHA-1 hash of one or more files.", category="Dev",
          usage="sha1sum <file> [file...]")
def cmd_sha1sum(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: sha1sum <file> [file...]")
        return
    for f in args:
        p = resolve_path(f)
        if not os.path.isfile(p):
            print(f"[ERROR] Not found: {p}")
            continue
        try:
            h = hashlib.sha1()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            print(f"  {h.hexdigest()}  {p}")
        except Exception as e:
            print(f"[ERROR] {e}")


@register("md5sum", "MD5 hash of one or more files.", category="Dev",
          usage="md5sum <file> [file...]")
def cmd_md5sum(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: md5sum <file> [file...]")
        return
    for f in args:
        p = resolve_path(f)
        if not os.path.isfile(p):
            print(f"[ERROR] Not found: {p}")
            continue
        try:
            h = hashlib.md5()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            print(f"  {h.hexdigest()}  {p}")
        except Exception as e:
            print(f"[ERROR] {e}")


@register("xxd", "Hex + ASCII dump of a file's first N bytes.",
          category="Dev", usage="xxd <file> [n]")
def cmd_xxd(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: xxd <file> [n]")
        return
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 512
    try:
        with open(resolve_path(args[0]), "rb") as f:
            data = f.read(limit)
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            h = " ".join(f"{b:02x}" for b in chunk)
            a = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"  {i:08x}: {h:<48}  {a}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("strings", "Extracts printable ASCII strings of length >= 4 from a binary file.",
          category="Dev", usage="strings <file> [min_len]")
def cmd_strings(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: strings <file> [min_len]")
        return
    min_len = int(args[1]) if len(args) > 1 and args[1].isdigit() else 4
    try:
        with open(resolve_path(args[0]), "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"[ERROR] {e}")
        return
    buf = []
    for b in data:
        if 32 <= b < 127:
            buf.append(chr(b))
        else:
            if len(buf) >= min_len:
                print("".join(buf))
            buf = []
    if len(buf) >= min_len:
        print("".join(buf))


@register("jqpath", "Navigates a JSON file with a dot path like user.name or items.0.id.",
          category="Dev", usage="jqpath <file> <path>",
          examples=["jqpath data.json user.name", "jqpath config.json servers.0.host"])
def cmd_jqpath(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: jqpath <file> <path>")
        return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] {e}")
        return
    cur = data
    parts = args[1].split(".")
    for p in parts:
        if p == "":
            continue
        try:
            if isinstance(cur, list):
                cur = cur[int(p)]
            else:
                cur = cur[p]
        except (KeyError, IndexError, ValueError, TypeError):
            print(f"[ERROR] Path not found: {args[1]}")
            return
    if isinstance(cur, (dict, list)):
        print(json.dumps(cur, indent=2))
    else:
        print(cur)


@register("jsoncheck", "Validates a JSON file and reports line/column of the first error.",
          category="Dev", usage="jsoncheck <file>")
def cmd_jsoncheck(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: jsoncheck <file>")
        return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8") as f:
            json.load(f)
        print("[ok] valid JSON")
    except json.JSONDecodeError as e:
        print(f"[ERROR] line {e.lineno}, col {e.colno}: {e.msg}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("venv", "Creates a Python virtual environment in the given directory.",
          category="Dev", usage="venv <dir>",
          examples=["venv .venv"])
def cmd_venv(args, stdin_text=None):
    target = resolve_path(args[0]) if args else resolve_path(".venv")
    try:
        subprocess.run([sys.executable, "-m", "venv", target], check=True, timeout=120)
        print(f"[ok] venv at {target}")
        print(f"  activate: {os.path.join(target, 'bin', 'activate' if not is_windows() else 'activate.bat')}")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] venv failed (exit {e.returncode})")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("pipfreeze", "Prints currently-installed Python packages (pip freeze).",
          category="Dev")
def cmd_pipfreeze(args, stdin_text=None):
    print(run_shell(f'"{sys.executable}" -m pip freeze', timeout=60))


@register("getenv", "Reads one environment variable, or 'all' to list them all.",
          category="Dev", usage="getenv <name>|all")
def cmd_getenv(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: getenv <name>|all")
        return
    if args[0].lower() == "all":
        for k, v in sorted(os.environ.items()):
            print(f"  {k}={v}")
        return
    val = os.environ.get(args[0])
    print(f"  {val}" if val is not None else f"[not set] {args[0]}")


@register("watchfile", "Watches a file and prints any new lines appended. Ctrl+C to stop.",
          category="Dev", usage="watchfile <file>",
          examples=["watchfile app.log"])
def cmd_watchfile(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: watchfile <file>")
        return
    p = resolve_path(args[0])
    if not os.path.isfile(p):
        print(f"[ERROR] Not found: {p}")
        return
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            print(f"[watchfile] tailing {p} (Ctrl+C to stop)")
            while True:
                line = f.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[watchfile] stopped")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  BATCH
# ============================================================
@register("findext", "Finds every file with a given extension under cwd.",
          category="Filesystem", usage="findext <ext>")
def cmd_findext(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: findext <ext>")
        return
    ext = args[0] if args[0].startswith(".") else "." + args[0]
    hits = 0
    for root, dirs, files in os.walk(STATE["cwd"]):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.lower().endswith(ext.lower()):
                print(os.path.join(root, f))
                hits += 1
                if hits >= 300:
                    print("[...truncated]")
                    return
    if hits == 0:
        print(f"[no {ext} files]")


@register("empty", "Finds zero-byte files under a directory.",
          category="Filesystem", usage="empty [path]")
def cmd_empty(args, stdin_text=None):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            full = os.path.join(root, f)
            try:
                if os.path.getsize(full) == 0:
                    print(f"  {full}")
                    count += 1
            except Exception:
                pass
    print(f"\n  {count} empty file(s)")


@register("bigfiles", "Lists the largest files under cwd.",
          category="Filesystem", usage="bigfiles [n]")
def cmd_bigfiles(args, stdin_text=None):
    n = int(args[0]) if args and args[0].isdigit() else 15
    files = []
    for root, dirs, fs in os.walk(STATE["cwd"]):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fs:
            full = os.path.join(root, f)
            try:
                files.append((os.path.getsize(full), full))
            except Exception:
                pass
    files.sort(reverse=True)
    print_header(f"Top {n} biggest files")
    for size, path in files[:n]:
        print(f"  {human_bytes(size):>10}  {path}")
    print()


# ============================================================
#  UTILITY
# ============================================================
@register("calc", "Arithmetic evaluator. Supports + - * / % ** and parentheses.",
          category="Utility", usage="calc <expr>",
          examples=["calc 2+2", "calc 10*3-5"])
def cmd_calc(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: calc <expr>")
        return
    import ast
    expr = " ".join(args)
    try:
        tree = ast.parse(expr, mode="eval")
        allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num,
                   ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div,
                   ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.FloorDiv)
        for node in ast.walk(tree):
            if not isinstance(node, allowed):
                print("[ERROR] Disallowed expression.")
                return
        result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {})
        print(f"  {result}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("random", "Random integer between two bounds. Defaults to 1–100.",
          category="Utility", usage="random [lo] [hi]")
def cmd_random(args, stdin_text=None):
    lo = int(args[0]) if args and args[0].lstrip("-").isdigit() else 1
    hi = int(args[1]) if len(args) > 1 and args[1].lstrip("-").isdigit() else 100
    print(f"  {random.randint(lo, hi)}")


@register("uuid", "Generates a random UUID v4.",
          category="Utility")
def cmd_uuid(args, stdin_text=None):
    import uuid as _u
    print(f"  {_u.uuid4()}")


@register("hash", "Hex-hashes text with md5, sha1, sha256, or sha512.",
          category="Utility", usage="hash <algo> <text>",
          examples=["hash sha256 hello", "hash md5 abc"])
def cmd_hash(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: hash <algo> <text>")
        return
    algo = args[0].lower()
    if algo not in ("md5", "sha1", "sha256", "sha512"):
        print("[ERROR] md5/sha1/sha256/sha512")
        return
    print(f"  {hashlib.new(algo, ' '.join(args[1:]).encode()).hexdigest()}")


@register("base64", "Base64-encodes text, or decodes it with -d.",
          category="Utility", usage="base64 [-d] <text>")
def cmd_base64(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: base64 [-d] <text>")
        return
    decode = args[0] == "-d"
    text = " ".join(args[1:] if decode else args)
    try:
        if decode:
            print(f"  {_b64.b64decode(text.encode()).decode()}")
        else:
            print(f"  {_b64.b64encode(text.encode()).decode()}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("now", "Current date and time as a single string.",
          category="Utility")
def cmd_now(args, stdin_text=None):
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@register("stopwatch", "Timed from now until you press Enter.",
          category="Utility")
def cmd_stopwatch(args, stdin_text=None):
    print("[stopwatch] Press Enter to stop...")
    start = time.time()
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
    print(f"  Elapsed: {time.time() - start:.2f} seconds")


@register("password", "Generates a random password. Default 16 chars.",
          category="Utility", usage="password [length]")
def cmd_password(args, stdin_text=None):
    length = int(args[0]) if args and args[0].isdigit() else 16
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    print(f"  {''.join(random.choice(chars) for _ in range(length))}")


@register("avg", "Sum, mean, min, and max of a list of numbers.",
          category="Utility", usage="avg <n1> <n2> ...")
def cmd_avg(args, stdin_text=None):
    try:
        nums = [float(a) for a in args]
    except ValueError:
        print("[ERROR] All numbers.")
        return
    if not nums:
        print("[ERROR] Need numbers.")
        return
    print(f"  Sum: {sum(nums)}  Avg: {sum(nums) / len(nums):.4f}")
    print(f"  Min: {min(nums)}  Max: {max(nums)}")


@register("prime", "Checks if a number is prime, and if not, prints the first divisor it finds.",
          category="Utility", usage="prime <n>")
def cmd_prime(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: prime <n>")
        return
    try:
        n = int(args[0])
    except ValueError:
        print("[ERROR] Integer needed.")
        return
    if n < 2:
        print(f"  {n} not prime.")
        return
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            print(f"  {n} not prime (÷{i})")
            return
    print(f"  {n} is prime.")


@register("factors", "Lists every integer divisor of the given number.",
          category="Utility", usage="factors <n>")
def cmd_factors(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: factors <n>")
        return
    try:
        n = abs(int(args[0]))
    except ValueError:
        print("[ERROR] Integer needed.")
        return
    print(f"  {n}: {[i for i in range(1, n + 1) if n % i == 0]}")


@register("timer", "Counts down N seconds, then beeps.",
          category="Utility", usage="timer <seconds>")
def cmd_timer(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: timer <seconds>")
        return
    try:
        n = int(args[0])
        for i in range(n, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        print("  [DONE]")
        print("\a", end="", flush=True)
    except (ValueError, KeyboardInterrupt):
        print("  [cancelled]")


@register("morse", "Converts text to Morse code.",
          category="Fun", usage="morse <text>")
def cmd_morse(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: morse <text>")
        return
    code = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
            "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
            "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
            "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
            "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
            "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
            "8": "---..", "9": "----.", " ": "/"}
    print("  " + " ".join(code.get(c, "?") for c in " ".join(args).upper()))


@register("caesar", "Shifts each letter by N positions in the alphabet.",
          category="Fun", usage="caesar <shift> <text>")
def cmd_caesar(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: caesar <shift> <text>")
        return
    try:
        shift = int(args[0])
    except ValueError:
        print("[ERROR] shift must be a number.")
        return
    out = ""
    for c in " ".join(args[1:]):
        if c.isalpha():
            base = ord("A") if c.isupper() else ord("a")
            out += chr((ord(c) - base + shift) % 26 + base)
        else:
            out += c
    print(f"  {out}")


@register("roll", "Rolls N dice with S sides. Format: NdS.",
          category="Fun", usage="roll <n>d<sides>",
          examples=["roll 2d6", "roll 1d20"])
def cmd_roll(args, stdin_text=None):
    if not args or "d" not in args[0]:
        print("[ERROR] Usage: roll <n>d<sides>")
        return
    try:
        n, s = args[0].lower().split("d")
        n = int(n) if n else 1
        s = int(s)
    except ValueError:
        print("[ERROR] Invalid format.")
        return
    rolls = [random.randint(1, s) for _ in range(n)]
    print(f"  Rolls: {rolls}")
    print(f"  Total: {sum(rolls)}")


@register("rps", "Plays rock-paper-scissors against the shell.",
          category="Fun", usage="rps <rock|paper|scissors>")
def cmd_rps(args, stdin_text=None):
    if not args or args[0].lower() not in ("rock", "paper", "scissors"):
        print("[ERROR] Usage: rps <rock|paper|scissors>")
        return
    player = args[0].lower()
    comp = random.choice(["rock", "paper", "scissors"])
    print(f"  You: {player}  Computer: {comp}")
    if player == comp:
        print("  Draw!")
    elif (player == "rock" and comp == "scissors") or \
         (player == "paper" and comp == "rock") or \
         (player == "scissors" and comp == "paper"):
        print("  You win!")
    else:
        print("  Computer wins.")


@register("luck", "Random luck score out of 100, with a bar.",
          category="Fun")
def cmd_luck(args, stdin_text=None):
    pct = random.randint(0, 100)
    bar = "#" * (pct // 5) + "." * (20 - pct // 5)
    print(f"  Luck: {pct}%  [{bar}]")


@register("coin", "Heads or tails.",
          category="Fun")
def cmd_coin(args, stdin_text=None):
    print(f"  {'HEADS' if random.randint(0, 1) == 0 else 'TAILS'}")


@register("dice", "Rolls one die. Default 6 sides.",
          category="Fun", usage="dice [sides]")
def cmd_dice(args, stdin_text=None):
    sides = int(args[0]) if args and args[0].isdigit() else 6
    print(f"  {random.randint(1, sides)}")


@register("shuffle", "Randomly reorders the arguments.",
          category="Fun", usage="shuffle <a> <b> ...")
def cmd_shuffle(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: shuffle <a> <b> ...")
        return
    items = list(args)
    random.shuffle(items)
    print(f"  {' '.join(items)}")


@register("pick", "Picks one of the arguments at random.",
          category="Fun", usage="pick <a> <b> ...")
def cmd_pick(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: pick <a> <b> ...")
        return
    print(f"  {random.choice(args)}")


@register("fortune", "Random fortune from a list.",
          category="Fun")
def cmd_fortune(args, stdin_text=None):
    fs = ["You will write a bug that haunts you for years.",
          "The bug is not in the code. It's in the assumptions.",
          "Take the nap. It's the answer.",
          "You will be productive tomorrow.",
          "Someone is thinking about you right now.",
          "A stranger will compliment your work.",
          "The stack overflow is on line 42.",
          "Someone out there loves you. Probably more than one."]
    print(f"  {random.choice(fs)}")


@register("quote", "Random programming quote and author.",
          category="Fun")
def cmd_quote(args, stdin_text=None):
    qs = [("Talk is cheap. Show me the code.", "Linus Torvalds"),
          ("Premature optimization is the root of all evil.", "Donald Knuth"),
          ("Code is like humor. When you have to explain it, it's bad.", "Cory House"),
          ("Simplicity is the soul of efficiency.", "Austin Freeman"),
          ("First, solve the problem. Then write the code.", "John Johnson")]
    q, a = random.choice(qs)
    print(f"  \"{q}\"")
    print(f"      - {a}")


@register("challenge", "Prints a random coding challenge.",
          category="Fun")
def cmd_challenge(args, stdin_text=None):
    cs = ["Return the nth Fibonacci in O(1) space.",
          "Reverse a linked list without extra memory.",
          "Find longest palindromic substring.",
          "Stack that returns minimum in O(1).",
          "Merge two sorted arrays in-place.",
          "Detect a cycle in a linked list."]
    print(f"  {random.choice(cs)}")


@register("cowsay", "A cow says whatever you give it.",
          category="Fun", usage="cowsay <text>")
def cmd_cowsay(args, stdin_text=None):
    text = " ".join(args) if args else "Hello from Eclipse Shell!"
    b = "-" * (len(text) + 2)
    print(f"  {b}")
    print(f"  {text}")
    print(f"  {b}")
    print("        \\   ^__^")
    print("         \\  (oo)\\_______")
    print("            (__)\\       )\\/\\")
    print("                ||----w |")
    print("                ||     ||")


@register("matrix", "Rain of 0s and 1s for a few seconds.",
          category="Fun")
def cmd_matrix(args, stdin_text=None):
    try:
        for _ in range(20):
            print("  " + "".join(random.choice("01 ") for _ in range(60)))
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass


@register("meme", "Random developer meme caption.",
          category="Fun")
def cmd_meme(args, stdin_text=None):
    ms = ["you got this", "ship it", "one more bug and then sleep",
          "it works on my machine", "delete node_modules and try again",
          "have you tried turning it off and on again",
          "80% done, 80% to go", "git commit -m 'fixed stuff'",
          "code is poetry. broken poetry."]
    print(f"  {random.choice(ms)}")


@register("progressbar", "Animates a progress bar for N seconds.",
          category="Fun", usage="progressbar [secs]")
def cmd_progressbar(args, stdin_text=None):
    secs = float(args[0]) if args and args[0].replace(".", "").isdigit() else 3.0
    for i in range(21):
        fill = i * 2
        bar = "#" * fill + "." * (40 - fill)
        sys.stdout.write(f"\r  [{bar}] {i * 5:3d}%")
        sys.stdout.flush()
        time.sleep(secs / 20)
    print()


@register("spinner", "Spinning loader for N seconds.",
          category="Fun", usage="spinner [secs]")
def cmd_spinner(args, stdin_text=None):
    secs = float(args[0]) if args and args[0].replace(".", "").isdigit() else 3.0
    frames = ["|", "/", "-", "\\"]
    end = time.time() + secs
    i = 0
    while time.time() < end:
        sys.stdout.write(f"\r  {frames[i % 4]} working...")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    print("\r  done.       ")


@register("beep", "Emits a beep at the given frequency for the given duration.",
          category="Fun", usage="beep [freq] [ms]")
def cmd_beep(args, stdin_text=None):
    freq = int(args[0]) if args and args[0].isdigit() else 1000
    dur = int(args[1]) if len(args) > 1 and args[1].isdigit() else 200
    try:
        if is_windows():
            import winsound
            winsound.Beep(freq, dur)
        elif is_android():
            subprocess.run("termux-vibrate -d 200", shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("\a", end="", flush=True)
        elif platform.system() == "Darwin":
            subprocess.run("osascript -e 'beep'", shell=True)
        else:
            print("\a", end="", flush=True)
        print("[beep]")
    except Exception:
        print("\a", end="", flush=True)
        print("[beep]")


@register("calendar", "Prints this month's calendar.",
          category="Utility")
def cmd_calendar(args, stdin_text=None):
    import calendar as c
    n = datetime.datetime.now()
    c.prmonth(n.year, n.month)


@register("timestamp", "Current Unix timestamp.",
          category="Utility")
def cmd_timestamp(args, stdin_text=None):
    print(f"  {int(time.time())}")


@register("daysuntil", "Days between now and the given date (YYYY-MM-DD).",
          category="Utility", usage="daysuntil YYYY-MM-DD")
def cmd_daysuntil(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: daysuntil YYYY-MM-DD")
        return
    try:
        t = datetime.datetime.strptime(args[0], "%Y-%m-%d")
        print(f"  {(t - datetime.datetime.now()).days} day(s)")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  PROCESS
# ============================================================
@register("tasklist", "Processes with PID and memory usage. Optional name filter.",
          category="Process", usage="tasklist [filter]")
def cmd_tasklist(args, stdin_text=None):
    procs = get_processes()
    if args:
        procs = [p for p in procs if args[0].lower() in p["name"].lower()]
    if not procs:
        print("[no processes]")
        return
    procs.sort(key=lambda p: p["mem_kb"], reverse=True)
    print_header(f"Processes - {len(procs)}")
    print(f"  {'PID':>7}  {'MEM':>10}  NAME")
    for p in procs:
        print(f"  {p['pid']:>7}  {human_kb(p['mem_kb']):>10}  {p['name']}")
    print()


@register("ps", "Alias of tasklist.",
          category="Process")
def cmd_ps(args, stdin_text=None):
    cmd_tasklist(args)


@register("top", "Top N processes by memory. Default 15.",
          category="Process", usage="top [n]")
def cmd_top(args, stdin_text=None):
    n = int(args[0]) if args and args[0].isdigit() else 15
    procs = get_processes()
    procs.sort(key=lambda p: p["mem_kb"], reverse=True)
    print_header(f"Top {n}")
    for p in procs[:n]:
        print(f"  {p['pid']:>7}  {human_kb(p['mem_kb']):>10}  {p['name']}")
    print()


@register("taskinfo", "Details for one process, looked up by PID or name.",
          category="Process", usage="taskinfo <pid|name>")
def cmd_taskinfo(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: taskinfo <pid|name>")
        return
    procs = get_processes()
    t = args[0]
    matches = ([p for p in procs if p["pid"] == int(t)] if t.isdigit()
               else [p for p in procs if t.lower() in p["name"].lower()])
    if not matches:
        print(f"[ERROR] No process: {t}")
        return
    for p in matches:
        print_header(f"Process: {p['name']}")
        print(f"  PID    : {p['pid']}")
        print(f"  Memory : {human_kb(p['mem_kb'])}")
        print(f"  User   : {p['user'] or '(unknown)'}")
        print()


@register("kill", "Force-terminates a process by PID.",
          category="Process", usage="kill <pid>")
def cmd_kill(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: kill <pid>")
        return
    cmd = f"taskkill /PID {args[0]} /F" if is_windows() else f"kill -9 {args[0]}"
    print(run_shell(cmd))


@register("battery", "Battery charge level on laptops or phones.",
          category="System")
def cmd_battery(args, stdin_text=None):
    if is_android():
        print(run_shell("termux-battery-status"))
    elif is_windows():
        print(run_shell("WMIC Path Win32_Battery Get EstimatedChargeRemaining"))
    else:
        print(run_shell("upower -i $(upower -e | grep BAT)"))


@register("storage", "Used and free space per drive.",
          category="System")
def cmd_storage(args, stdin_text=None):
    print(run_shell("wmic logicaldisk get size,freespace,caption"
                    if is_windows() else "df -h"))


@register("apps", "Lists installed Android packages (Termux).",
          category="System")
def cmd_apps(args, stdin_text=None):
    if not is_android():
        print("[ERROR] Android only.")
        return
    print(run_shell("pm list packages | head -50"))


# ============================================================
#  START
# ============================================================
@register("start", "Launches a program by name from PATH or disk.",
          category="System", usage="start <program> [args...]")
def cmd_start(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: start <program> [args...]")
        return
    path = find_program(args[0])
    if not path:
        print(f"[ERROR] Not found: {args[0]}")
        return
    try:
        if is_windows():
            subprocess.Popen(["start", "", path] + args[1:], shell=True)
        else:
            subprocess.Popen([path] + args[1:],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL,
                             start_new_session=True)
        print(f"[start] Launched: {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  NETWORK
# ============================================================
@register("wlan", "Lists saved Wi-Fi profiles. 'wlan profile <name>' reveals a saved password.",
          category="Network", usage="wlan [profile <name>]")
def cmd_wlan(args, stdin_text=None):
    if is_windows():
        if args and args[0].lower() == "profile" and len(args) >= 2:
            print(run_shell(f'netsh wlan show profile name="{args[1]}" key=clear', timeout=30))
        else:
            print(run_shell("netsh wlan show profile", timeout=30))
    elif is_android():
        print(run_shell("dumpsys wifi | grep -i ssid"))
    else:
        print("[ERROR] Windows/Android only.")


@register("ping", "Pings a host. Second arg sets packet count.",
          category="Network", usage="ping <host> [count]")
def cmd_ping(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: ping <host> [count]")
        return
    count = args[1] if len(args) > 1 else "4"
    flag = "-n" if is_windows() else "-c"
    run_shell(f"ping {flag} {count} {args[0]}", live=True)


@register("ip", "Prints IP configuration for all network adapters.",
          category="Network")
def cmd_ip(args, stdin_text=None):
    print(run_shell("ipconfig" if is_windows() else "ip addr || ifconfig"))


@register("ifconfig", "Alias of ip.",
          category="Network")
def cmd_ifconfig(args, stdin_text=None):
    cmd_ip(args)


@register("netstat", "Lists active network connections.",
          category="Network")
def cmd_netstat(args, stdin_text=None):
    print(run_shell("netstat -an"))


@register("route", "Prints the routing table.",
          category="Network")
def cmd_route(args, stdin_text=None):
    print(run_shell("route print" if is_windows() else "ip route || route -n"))


@register("arp", "Prints the ARP table.",
          category="Network")
def cmd_arp(args, stdin_text=None):
    print(run_shell("arp -a"))


@register("nslookup", "DNS lookup for a hostname.",
          category="Network", usage="nslookup <host>")
def cmd_nslookup(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: nslookup <host>")
        return
    print(run_shell(f"nslookup {args[0]}"))


@register("tracert", "Shows each network hop between you and a host.",
          category="Network", usage="tracert <host>")
def cmd_tracert(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: tracert <host>")
        return
    print(f"[tracert] tracing {args[0]}...")
    sys.stdout.flush()
    cmd = (f"tracert -d -w 1000 -h 15 {args[0]}" if is_windows()
           else f"traceroute -n -w 1 -m 15 {args[0]}")
    try:
        subprocess.run(cmd, shell=True, timeout=90)
    except subprocess.TimeoutExpired:
        print("\n[tracert] timed out")
    except KeyboardInterrupt:
        print("\n[tracert] cancelled")


@register("localip", "Prints this machine's IP on the local network.",
          category="Network")
def cmd_localip(args, stdin_text=None):
    import socket as s
    try:
        sock = s.socket(s.AF_INET, s.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        print(f"  {sock.getsockname()[0]}")
        sock.close()
    except Exception as e:
        print(f"[ERROR] {e}")


@register("publicip", "Prints this machine's public IP as seen from the internet.",
          category="Network")
def cmd_publicip(args, stdin_text=None):
    print(run_shell("curl -s https://api.ipify.org", timeout=15))


@register("port", "Checks whether a TCP port is open on a host.",
          category="Network", usage="port <host> <port>")
def cmd_port(args, stdin_text=None):
    if len(args) < 2:
        print("[ERROR] Usage: port <host> <port>")
        return
    import socket as s
    try:
        p = int(args[1])
    except ValueError:
        print("[ERROR] Port must be a number.")
        return
    sock = s.socket(s.AF_INET, s.SOCK_STREAM)
    sock.settimeout(3)
    try:
        r = sock.connect_ex((args[0], p))
        print(f"[{'open' if r == 0 else 'closed'}] {args[0]}:{p}")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        sock.close()


@register("curl", "Fetches a URL and prints the raw response body.",
          category="Network", usage="curl <url>",
          examples=["curl https://example.com", "curl https://api.ipify.org"])
def cmd_curl(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: curl <url>")
        return
    print(run_shell(f"curl -s {args[0]}", timeout=30))


@register("wget", "Fetches a URL. Unix-only; on Windows use curl.",
          category="Network", usage="wget <url>")
def cmd_wget(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: wget <url>")
        return
    if is_windows():
        print("[ERROR] wget not on Windows.")
        return
    print(run_shell(f"wget -qO- {args[0]}", timeout=30))


# ============================================================
#  USER / POWER
# ============================================================
@register("cu", "Changes the shell username shown in the prompt.",
          category="System", usage="cu <new_username>")
def cmd_cu(args, stdin_text=None):
    if not args:
        print("[ERROR] Usage: cu <new_username>")
        return
    old = STATE["user"]
    STATE["user"] = args[0]
    print(f"[user] '{old}' -> '{args[0]}'")


@register("shutdown", "Shuts down, restarts, or aborts a shutdown on this PC. Windows only.",
          category="Power", usage="shutdown [s|r|a] [seconds]",
          examples=["shutdown", "shutdown r 30", "shutdown a"])
def cmd_shutdown(args, stdin_text=None):
    if not is_windows():
        print("[ERROR] Windows only.")
        return
    if not args:
        cmd = "shutdown /s /t 0"
    else:
        mode = args[0].lower()
        secs = args[1] if len(args) > 1 else "0"
        if mode in ("s", "shutdown"):
            cmd = f"shutdown /s /t {secs}"
        elif mode in ("r", "restart", "reboot"):
            cmd = f"shutdown /r /t {secs}"
        elif mode in ("a", "abort"):
            cmd = "shutdown /a"
        else:
            print("[ERROR] Usage: shutdown [s|r|a] [seconds]")
            return
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       encoding=console_encoding(), errors="replace")
    if r.returncode != 0:
        print(f"[ERROR] shutdown failed (code {r.returncode})")
    else:
        print("[ok] Shutdown command sent.")


@register("reboot", "Restarts this PC immediately.",
          category="Power")
def cmd_reboot(args, stdin_text=None):
    if is_windows():
        r = subprocess.run("shutdown /r /t 0", shell=True, capture_output=True,
                           text=True, encoding=console_encoding(), errors="replace")
        if r.returncode != 0:
            print(f"[ERROR] reboot failed (code {r.returncode})")
        else:
            print("[ok] Reboot command sent.")
    elif is_android():
        print(run_shell("su -c 'reboot' || echo '[ERROR] root required'"))
    else:
        print("[ERROR] Windows/Android only.")


# ============================================================
#  PIPE + REDIRECT
# ============================================================
STDIN_CONSUMERS = {
    "grep", "wc", "sort", "uniq", "head", "tail",
    "lines", "upper", "lower", "rev",
}


def _run_with_capture(name, args, stdin_text=None):
    """Run a command, capturing its stdout. Returns (output, error)."""
    target = COMMANDS.get(name)
    if not target:
        return None, f"[ERROR] Unknown: {name}"
    fn = target["fn"]
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    err = None
    try:
        if stdin_text is not None and name in STDIN_CONSUMERS:
            try:
                fn(args, stdin_text)
            except TypeError:
                fn(args)
        else:
            fn(args)
    except SystemExit:
        raise
    except Exception as e:
        err = f"[ERROR] {e}"
    finally:
        sys.stdout = old
    return buf.getvalue(), err


def run_pipeline(line):
    segments = [s.strip() for s in line.split("|") if s.strip()]
    if not segments:
        return
    stdin_text = None
    for i, seg in enumerate(segments):
        parts = seg.split()
        if not parts:
            continue
        name = parts[0].lower().rstrip("()")
        args = parts[1:]
        is_last = (i == len(segments) - 1)
        out, err = _run_with_capture(name, args, stdin_text)
        if err:
            print(err)
            return
        if is_last:
            if out:
                print(out, end="" if out.endswith("\n") else "\n")
        else:
            stdin_text = out or ""


def run_redirect(line):
    if ">>" in line:
        left, right = line.split(">>", 1)
        append = True
    elif ">" in line:
        left, right = line.split(">", 1)
        append = False
    else:
        return False
    left = left.strip()
    right = right.strip().strip('"').strip("'")
    if not left or not right:
        print("[ERROR] Missing command or file.")
        return True
    target = resolve_path(right)
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        dispatch(left)
    except SystemExit:
        raise
    except Exception as e:
        sys.stdout = old
        print(f"[ERROR] {e}")
        return True
    finally:
        sys.stdout = old
    out = buf.getvalue()
    try:
        with open(target, "a" if append else "w", encoding="utf-8") as f:
            f.write(out)
        print(f"[redirect] {'Appended' if append else 'Wrote'} to {target}")
    except Exception as e:
        print(f"[ERROR] {e}")
    return True


# ============================================================
#  TAB COMPLETION
# ============================================================
def completer(text, state):
    if readline is None:
        return None
    opts = [c for c in COMMANDS.keys() if c.startswith(text)]
    opts += [a for a in STATE["aliases"].keys() if a.startswith(text)]
    return opts[state] if state < len(opts) else None


# ============================================================
#  DISPATCH
# ============================================================
def dispatch(line):
    parts = line.strip().split()
    if not parts:
        return

    first = parts[0]
    if first in STATE["aliases"]:
        line = STATE["aliases"][first] + " " + " ".join(parts[1:])
        parts = line.strip().split()
        if not parts:
            return

    STATE["history"].append(line.strip())
    name = parts[0].lower().rstrip("()")
    args = parts[1:]
    cmd = COMMANDS.get(name)
    if not cmd:
        print(f"[ERROR] Unknown command: {name}   (type 'help')")
        return
    try:
        cmd["fn"](args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  BANNER
# ============================================================
def banner():
    # Count is computed from the live registry, never hardcoded.
    n = len(COMMANDS)

    # Detect duplicate @register decorators. register() silently overwrites,
    # so duplicates are invisible in COMMANDS but visible in the source.
    dupes = []
    try:
        import ast, inspect
        src = inspect.getsource(sys.modules[__name__])
        tree = ast.parse(src)
        seen = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "register"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)):
                nm = node.args[0].value
                seen[nm] = seen.get(nm, 0) + 1
        dupes = sorted(k for k, v in seen.items() if v > 1)
    except Exception:
        pass

    print(r"""
 ███████╗ ██████╗██╗     ██╗██████╗ ███████╗███████╗
 ██╔════╝██╔════╝██║     ██║██╔══██╗██╔════╝██╔════╝
 █████╗  ██║     ██║     ██║██████╔╝███████╗█████╗
 ██╔══╝  ██║     ██║     ██║██╔═══╝ ╚════██║██╔══╝
 ███████╗╚██████╗███████╗██║██║     ███████║███████╗
 ╚══════╝ ╚═════╝╚══════╝╚═╝╚═╝     ╚══════╝╚══════╝

        ███████╗██╗  ██╗███████╗██╗     ██╗
        ██╔════╝██║  ██║██╔════╝██║     ██║
        ███████╗███████║█████╗  ██║     ██║
        ╚════██║██╔══██║██╔══╝  ██║     ██║
        ███████║██║  ██║███████╗███████╗███████╗
        ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
    """)
    print(f"  Eclipse Shell Version {STATE['version']} ({STATE['status']})")
    print(f"  Copyright (c) 2026 {STATE['author']}")
    print("  Type 'help' for commands, 'man <cmd>' for details.")
    print(f"  {n} commands registered.")
    if dupes:
        print(f"  [WARN] duplicate registrations: {', '.join(dupes)}")
    if HAS_PSUTIL:
        print(f"  psutil detected — process listing is fast.")
    print()


# ============================================================
#  MAIN
# ============================================================
def main():
    if readline is not None:
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")

    banner()
    while True:
        try:
            line = input(prompt())
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            if ">" in line:
                run_redirect(line)
            elif "|" in line:
                run_pipeline(line)
            else:
                dispatch(line)
        except SystemExit:
            break


if __name__ == "__main__":
    main()
