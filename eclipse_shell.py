#!/usr/bin/env python3
"""
Eclipse Shell
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

# Optional readline for up-arrow history
try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        readline = None

# ============================================================
#  STATE
# ============================================================
STATE = {
    "cwd": os.getcwd(),
    "user": "eclipse",
    "host": "eclipse",
    "history": [],
    "version": "0.5.0",
    "status": "indev",
    "author": "ilikehamandcheese11",
    "youtube": "https://www.youtube.com/@ilikehamandcheese11",
    "discord": "@ilikehamandcheese11",
    "aliases": {},
}

COMMANDS = {}

RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
BLUE = "\033[94m"; MAGENTA = "\033[95m"; CYAN = "\033[96m"; WHITE = "\033[97m"
BG_RED = "\033[41m"; BG_YEL = "\033[43m"; BG_GRN = "\033[42m"; BG_BLU = "\033[44m"

RESERVED = {"help","exit","quit","cd","cls","clear","call","alias","unalias","man"}


def register(name, desc=""):
    def wrapper(fn):
        COMMANDS[name] = {"fn": fn, "desc": desc or fn.__doc__ or ""}
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


# ============================================================
#  HELPERS
# ============================================================
def prompt():
    return f"{STATE['user']}@{STATE['host']}> "


def print_header(title):
    print("=" * 50)
    print(f"  {title}")
    print("=" * 50)


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
        
        # Fix Windows encoding issues (CP866/CP1251) by using the system's preferred encoding
        enc = "utf-8" if not is_windows() else "cp866"
        
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding=enc, errors="replace", timeout=timeout,
        )
        out = result.stdout or ""
        if result.stderr:
            out += "\n[stderr]\n" + result.stderr
        return out if out.strip() else "[no output]"
    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out."
    except Exception as e:
        return f"[ERROR] {e}"


def _safe_run(cmd, timeout=15):
    try:
        enc = "utf-8" if not is_windows() else "cp866"
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding=enc, errors="replace", timeout=timeout,
        )
        return r.stdout or ""
    except Exception:
        return ""


def human_kb(kb):
    if kb < 1024: return f"{kb} K"
    mb = kb / 1024
    if mb < 1024: return f"{mb:.1f} MB"
    return f"{mb/1024:.2f} GB"


def human_bytes(b):
    try: b = float(b)
    except (TypeError, ValueError): return "?"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.2f} {unit}" if unit != "B" else f"{b:.0f} B"
        b /= 1024
    return f"{b:.2f} PB"


# ============================================================
#  PROCESSES
# ============================================================
def get_processes():
    procs = []
    try:
        if is_windows():
            out = subprocess.run(
                'tasklist /FO CSV /NH', shell=True, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=20,
            ).stdout or ""
            reader = csv.reader(io.StringIO(out))
            for row in reader:
                if len(row) >= 5:
                    try: pid_int = int(row[1])
                    except ValueError: pid_int = 0
                    try: mem_kb = int(row[4].replace(",", "").replace(" K", "").strip())
                    except ValueError: mem_kb = 0
                    procs.append({"pid": pid_int, "name": row[0], "mem_kb": mem_kb, "user": ""})
        else:
            out = subprocess.run(
                'ps -eo pid,user,comm,rss', shell=True, capture_output=True,
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
#  SYSTEM INFO
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
                elif "Hardware" in line and "cpu_name" not in info:
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
        v = _safe_run("getprop ro.build.version.release", timeout=5).strip()
        if v: info["android_version"] = v
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
#  PATHFINDER
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
        make the Software available to any third party, whether
        for free or for a fee.

     b) Sell, resell, sublicense, rent, lease, or otherwise
        commercialize the Software.

     c) Modify, adapt, translate, reverse-engineer, decompile,
        disassemble, or create derivative works based on the
        Software.

     d) Remove, alter, or obscure any copyright notice,
        attribution, license text, or branding contained in the
        Software.

     e) Claim authorship, ownership, or credit for the Software
        or any part of it.

     f) Rebrand, rename, or present the Software under a
        different name or identity.

     g) Use the Software as part of a larger product offered for
        sale without explicit written permission from the Author.

     h) Use the Software for any unlawful purpose or in violation
        of applicable laws or regulations.

4. THIRD-PARTY COMPONENTS

   The Software may reference or invoke third-party programs,
   libraries, or services. Use of those components is governed
   by their own respective licenses. This License applies only
   to Eclipse Shell itself.

5. NO WARRANTY

   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
   OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
   NON-INFRINGEMENT. THE AUTHOR MAKES NO WARRANTY THAT THE SOFTWARE
   WILL BE ERROR-FREE, SECURE, OR UNINTERRUPTED.

6. LIMITATION OF LIABILITY

   IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES,
   OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR
   OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE
   SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

   This includes, without limitation, any damages resulting from:

     - Data loss or corruption
     - System malfunction or hardware damage
     - Unintended execution of commands
     - Security breaches or unauthorized access
     - Any indirect, incidental, or consequential damages

   The user assumes full responsibility for any commands executed
   through the Software and any consequences thereof.

7. USER RESPONSIBILITY

   Eclipse Shell is a command shell capable of executing system
   commands. You acknowledge and agree that:

     a) You are solely responsible for the commands you run.

     b) You will not use the Software to harm, disrupt, or gain
        unauthorized access to any system, network, or device.

     c) You will comply with all applicable laws while using the
        Software.

8. TERMINATION

   This License is effective until terminated. It will terminate
   automatically without notice if you breach any of its terms.
   Upon termination, you must immediately cease all use of the
   Software and destroy all copies in your possession.

   The Author reserves the right to revoke or modify this License
   at any time, at their sole discretion.

9. ENFORCEMENT

   Unauthorized use, copying, distribution, or modification of
   the Software constitutes copyright infringement and may result
   in civil and/or criminal penalties under applicable law. The
   Author reserves the right to pursue all available legal
   remedies.

10. CONTACT

    For permissions, licensing inquiries, or commercial use
    requests:

      Author  : ilikehamandcheese11
      YouTube : https://www.youtube.com/@ilikehamandcheese11
      Discord : @ilikehamandcheese11

================================================================
   By using Eclipse Shell, you acknowledge that you have read,
   understood, and agree to be bound by the terms of this License.
   If you do not agree, you must not use the Software.
================================================================
"""


# ============================================================
#  CORE COMMANDS
# ============================================================
@register("help", "List all available commands.")
def cmd_help(args):
    print_header("Eclipse Shell - Command List")
    for name in sorted(COMMANDS.keys()):
        print(f"  {name:<16} {COMMANDS[name]['desc']}")
    print()


@register("man", "Detailed help for a command.  Usage: man <command>")
def cmd_man(args):
    if not args:
        print("[ERROR] Usage: man <command>")
        return
    name = args[0].lower().rstrip("()")
    if name not in COMMANDS:
        print(f"[ERROR] Unknown command: {name}")
        return
    print_header(f"man {name}")
    print(f"  {COMMANDS[name]['desc']}")
    print()


@register("about", "Show info about Eclipse Shell.")
def cmd_about(args):
    print_header("About Eclipse Shell")
    print(f"  Name     : Eclipse Shell")
    print(f"  Version  : {STATE['version']} ({STATE['status']})")
    print(f"  Author   : {STATE['author']}")
    print(f"  License  : Proprietary")
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {platform.python_version()}")
    print()
    print("  Cross-platform terminal for Windows, Linux, macOS, and Android.")
    print()
    print(f"  Contact  : YouTube {STATE['youtube']}  |  Discord {STATE['discord']}")
    print()


@register("license", "Display the license.")
def cmd_license(args):
    print(LICENSE_TEXT)


@register("cls", "Clear screen.")
def cmd_cls(args):
    if is_windows(): os.system("")
    sys.stdout.write("\033[2J\033[3J\033[H")
    sys.stdout.flush()


@register("clear", "Clear screen (alias).")
def cmd_clear(args):
    cmd_cls(args)


@register("exit", "Exit Eclipse Shell.")
def cmd_exit(args):
    print("Shutting down Eclipse Shell...")
    raise SystemExit(0)


@register("quit", "Exit Eclipse Shell.")
def cmd_quit(args):
    cmd_exit(args)


@register("history", "Show command history.")
def cmd_history(args):
    if not STATE["history"]:
        print("[empty]")
        return
    for i, h in enumerate(STATE["history"], 1):
        print(f"  {i:>4}  {h}")


@register("version", "Show version.")
def cmd_version(args):
    print(f"Eclipse Shell [Version {STATE['version']} {STATE['status']}]")


@register("ver", "Show version (alias).")
def cmd_ver(args):
    cmd_version(args)


@register("commands", "Count registered commands.")
def cmd_commands(args):
    print(f"  {len(COMMANDS)} commands registered")


@register("allhelp", "Compact command grid.")
def cmd_allhelp(args):
    names = sorted(COMMANDS.keys())
    print(f"  {len(names)} commands:")
    for i in range(0, len(names), 5):
        print("  " + "  ".join(f"{n:<14}" for n in names[i:i+5]))


@register("tips", "Random tip.")
def cmd_tips(args):
    tips = ["Pipes: tasklist | grep chrome", "Redirect: dir > files.txt",
            "Smart launch: start notepad", "Specs: sysinfo",
            "Tree: tree", "Search: findext py",
            "Banner: banner ECLIPSE", "History: press up arrow"]
    print(f"  Tip: {random.choice(tips)}")


@register("pkglist", "List commands by category.")
def cmd_pkglist(args):
    print_header("Categories")
    cats = {
        "Filesystem": ["cd","pwd","dir","ls","type","cat","mkdir","rm","rmdir","find","grep","head","tail","wc","df","cp","mv","touch","write","append","rename","tree","size","lsd","lsf","countfiles","makedirs","pwdshort","which","fileinfo"],
        "System": ["sysinfo","os","cpu","mem","gpu","hostname","user","env","time","date","uptime","temp","proc","top5","services","startup","drivers","info"],
        "Process": ["tasklist","ps","top","taskinfo","kill","battery","storage","apps"],
        "Network": ["wlan","ping","ip","ifconfig","netstat","route","arp","nslookup","tracert","localip","publicip","port","curl","wget","netcheck"],
        "Text": ["sort","uniq","rev","replace","lines","join","split","diff","upper","lower","swap","sed","regex","wc-lines"],
        "Dev": ["py","json","hex","count","todo","jwt","url","epoch","uuid","uuid7"],
        "Batch": ["findext","empty","bigfiles","du"],
        "Archive": ["zip","unzip","tar","untar","clip","paste"],
        "Utility": ["calc","random","hash","base64","now","stopwatch","password","unitconvert","bmi","avg","prime","factors","timer","morse","caesar","roll","rps","watch","bench"],
        "Shell": ["help","man","about","license","version","ver","history","call","commands","allhelp","tips","clrhist","last","repeat","wait","alias","unalias"],
        "Fun": ["cowsay","matrix","meme","fortune","quote","dice","coin","luck","shuffle","pick","beep","progressbar","spinner","banner","challenge"],
        "Power": ["shutdown","reboot"],
    }
    for cat, cmds in cats.items():
        present = [c for c in cmds if c in COMMANDS]
        if present:
            print(f"  {cat}: {' '.join(present)}")
    print()


@register("info", "Compact system summary.")
def cmd_info(args):
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


@register("clrhist", "Clear history.")
def cmd_clrhist(args):
    STATE["history"].clear()
    print("[ok] History cleared")


@register("last", "Show last command.")
def cmd_last(args):
    print(f"  {STATE['history'][-1]}" if STATE["history"] else "[empty]")


@register("repeat", "Repeat a command N times.")
def cmd_repeat(args):
    if len(args) < 2:
        print("[ERROR] Usage: repeat <n> <command>")
        return
    try: n = int(args[0])
    except ValueError:
        print("[ERROR] n must be number.")
        return
    for i in range(n):
        print(f"--- run {i+1}/{n} ---")
        dispatch(" ".join(args[1:]))


@register("wait", "Wait N seconds.")
def cmd_wait(args):
    if not args:
        print("[ERROR] Usage: wait <seconds>")
        return
    try:
        n = float(args[0])
        time.sleep(n)
        print(f"[ok] waited {n}s")
    except (ValueError, KeyboardInterrupt):
        print("[cancelled]")


@register("alias", "Create a command alias.  Usage: alias <name>=<value>")
def cmd_alias(args):
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


@register("unalias", "Remove an alias.  Usage: unalias <name>")
def cmd_unalias(args):
    if not args:
        print("[ERROR] Usage: unalias <name>")
        return
    name = args[0]
    if name in STATE["aliases"]:
        del STATE["aliases"][name]
        print(f"[alias] removed {name}")
    else:
        print(f"[ERROR] No alias: {name}")


@register("which", "Locate a command or file.  Usage: which <name>")
def cmd_which(args):
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


@register("watch", "Repeat a command every N seconds.  Usage: watch <secs> <cmd>")
def cmd_watch(args):
    if len(args) < 2:
        print("[ERROR] Usage: watch <secs> <command>")
        return
    try: secs = float(args[0])
    except ValueError:
        print("[ERROR] secs must be a number.")
        return
    cmd = " ".join(args[1:])
    try:
        while True:
            os.system("cls" if is_windows() else "clear")
            print(f"[watch] every {secs}s: {cmd}")
            print("-" * 50)
            dispatch(cmd)
            time.sleep(secs)
    except KeyboardInterrupt:
        print("\n[watch] stopped")


@register("bench", "Quick CPU benchmark.")
def cmd_bench(args):
    print("[bench] running...")
    start = time.time()
    total = 0
    for i in range(1, 500000):
        total += i * i
    elapsed = time.time() - start
    score = int(500000 / elapsed)
    print(f"  Time   : {elapsed:.3f}s")
    print(f"  Score  : {score} (higher = faster)")


@register("banner", "Print big ASCII banner.  Usage: banner <text>")
def cmd_banner(args):
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


@register("epoch", "Convert Unix timestamp.  Usage: epoch [timestamp]")
def cmd_epoch(args):
    if not args:
        print(f"  now: {int(time.time())}")
        return
    try:
        ts = int(args[0])
        dt = datetime.datetime.fromtimestamp(ts)
        print(f"  {ts} -> {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    except ValueError:
        try:
            dt = datetime.datetime.strptime(args[0], "%Y-%m-%d")
            print(f"  {args[0]} -> {int(dt.timestamp())}")
        except Exception as e:
            print(f"[ERROR] {e}")


@register("uuid7", "Generate a time-sortable UUID (simulated).")
def cmd_uuid7(args):
    import uuid as _u
    ts = int(time.time() * 1000)
    rand = _u.uuid4().hex[8:]
    print(f"  {ts:012x}-{rand[:4]}-{rand[4:8]}-{rand[8:12]}-{rand[12:24]}")


@register("url", "URL encode/decode.  Usage: url [-d] <text>")
def cmd_url(args):
    if not args:
        print("[ERROR] Usage: url [-d] <text>")
        return
    decode = args[0] == "-d"
    text = " ".join(args[1:] if decode else args)
    try:
        if decode:
            print(f"  {urllib.parse.unquote(text)}")
        else:
            print(f"  {urllib.parse.quote(text)}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("jwt", "Decode a JWT (no verification).  Usage: jwt <token>")
def cmd_jwt(args):
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


@register("regex", "Test a regex.  Usage: regex <pattern> <text>")
def cmd_regex(args):
    if len(args) < 2:
        print("[ERROR] Usage: regex <pattern> <text>")
        return
    try:
        pattern = args[0]
        text = " ".join(args[1:])
        m = re.search(pattern, text)
        if m:
            print(f"  match: '{m.group()}'")
            for i, g in enumerate(m.groups(), 1):
                print(f"  group {i}: {g}")
        else:
            print("  no match")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("sed", "Find/replace in a file.  Usage: sed <file> <pattern> <replacement>")
def cmd_sed(args):
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


@register("wc-lines", "Count lines across files.  Usage: wc-lines [path]")
def cmd_wc_lines(args):
    target = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(target):
        print(f"[ERROR] Not a directory: {target}")
        return
    total = 0
    for root, dirs, files in os.walk(target):
        for f in files:
            if not f.endswith((".py",".txt",".md",".js",".ts",".c",".cpp",".h")):
                continue
            full = os.path.join(root, f)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    n = sum(1 for _ in fh)
                total += n
                print(f"  {n:>6}  {full}")
            except Exception: pass
    print(f"\n  Total: {total} lines")


@register("du", "Directory size (recursive).")
def cmd_du(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.exists(path):
        print(f"[ERROR] Not found: {path}")
        return
    if os.path.isfile(path):
        print(f"{human_bytes(os.path.getsize(path))}  {path}")
        return
    total = 0; count = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
                count += 1
            except Exception: pass
    print(f"{human_bytes(total)}  {count} files  {path}")


@register("fileinfo", "Detect file type by magic bytes.")
def cmd_fileinfo(args):
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
            b"\x89PNG": "PNG image",
            b"\xff\xd8\xff": "JPEG image",
            b"GIF8": "GIF image",
            b"PK\x03\x04": "ZIP archive",
            b"%PDF": "PDF document",
            b"MZ": "Windows executable",
            b"\x7fELF": "Linux executable",
            b"ID3": "MP3 audio",
            b"OggS": "OGG media",
            b"RIFF": "RIFF media",
        }
        kind = "unknown"
        for sig, name in sigs.items():
            if head.startswith(sig):
                kind = name
                break
        size = os.path.getsize(path)
        print(f"  Path  : {path}")
        print(f"  Type  : {kind}")
        print(f"  Size  : {human_bytes(size)}")
        print(f"  Magic : {head[:8].hex()}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("netcheck", "Ping + DNS + traceroute in one.")
def cmd_netcheck(args):
    if not args:
        print("[ERROR] Usage: netcheck <host>")
        return
    host = args[0]
    print(f"[netcheck] {host}")
    print("-" * 50)
    print("[DNS]")
    print(_safe_run(f"nslookup {host}", timeout=10) or "[no output]")
    print("[PING]")
    flag = "-n" if is_windows() else "-c"
    print(_safe_run(f"ping {flag} 2 {host}", timeout=15) or "[no output]")


# ============================================================
#  FILESYSTEM
# ============================================================
@register("cd", "Change directory.")
def cmd_cd(args):
    if not args:
        print(STATE["cwd"]); return
    t = resolve_path(args[0])
    if os.path.isdir(t): STATE["cwd"] = t
    else: print(f"[ERROR] Not a directory: {t}")


@register("pwd", "Print working directory.")
def cmd_pwd(args):
    print(STATE["cwd"])


@register("pwdshort", "Just the folder name.")
def cmd_pwdshort(args):
    print(os.path.basename(STATE["cwd"]) or STATE["cwd"])


@register("dir", "List directory.")
def cmd_dir(args):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(t): print(f"[ERROR] Not a dir: {t}"); return
    try: entries = sorted(os.listdir(t))
    except PermissionError: print(f"[ERROR] Access denied."); return
    if not entries: print("[empty]"); return
    for e in entries:
        tag = "<DIR>" if os.path.isdir(os.path.join(t, e)) else "     "
        print(f"  {tag}  {e}")


@register("ls", "List (Unix).")
def cmd_ls(args):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(t): print(f"[ERROR] Not a dir: {t}"); return
    for e in sorted(os.listdir(t)):
        print(e + ("/" if os.path.isdir(os.path.join(t, e)) else ""))


@register("lsd", "List dirs only.")
def cmd_lsd(args):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    dirs = [d for d in sorted(os.listdir(t)) if os.path.isdir(os.path.join(t, d))]
    for d in dirs: print(d + "/")
    if not dirs: print("[no directories]")


@register("lsf", "List files only.")
def cmd_lsf(args):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    files = [f for f in sorted(os.listdir(t)) if os.path.isfile(os.path.join(t, f))]
    for f in files: print(f"  {human_bytes(os.path.getsize(os.path.join(t, f))):>10}  {f}")
    if not files: print("[no files]")


@register("countfiles", "Count files and dirs.")
def cmd_countfiles(args):
    t = resolve_path(args[0]) if args else STATE["cwd"]
    nf = nd = 0
    for root, dirs, files in os.walk(t):
        nf += len(files); nd += len(dirs)
    print(f"  Files: {nf}\n  Dirs : {nd}")


@register("makedirs", "Create multiple dirs.")
def cmd_makedirs(args):
    if not args: print("[ERROR] Usage: makedirs <d1> <d2>..."); return
    for d in args:
        try:
            os.makedirs(resolve_path(d), exist_ok=True)
            print(f"  [ok] {d}")
        except Exception as e: print(f"  [ERROR] {d}: {e}")


@register("type", "Print file.")
def cmd_type(args):
    if not args: print("[ERROR] Missing file."); return
    p = resolve_path(args[0])
    if not os.path.isfile(p): print(f"[ERROR] File not found: {p}"); return
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f: print(f.read())
    except Exception as e: print(f"[ERROR] {e}")


@register("cat", "Print file (alias).")
def cmd_cat(args): cmd_type(args)


@register("mkdir", "Create directory.")
def cmd_mkdir(args):
    if not args: print("[ERROR] Usage: mkdir <name>"); return
    try:
        os.makedirs(resolve_path(args[0]), exist_ok=True)
        print(f"[ok] Created {resolve_path(args[0])}")
    except Exception as e: print(f"[ERROR] {e}")


@register("rm", "Remove file.")
def cmd_rm(args):
    if not args: print("[ERROR] Usage: rm <file>"); return
    p = resolve_path(args[0])
    if not os.path.exists(p): print(f"[ERROR] Not found: {p}"); return
    try:
        if os.path.isdir(p): print("[ERROR] Use rmdir."); return
        os.remove(p); print(f"[ok] Removed {p}")
    except Exception as e: print(f"[ERROR] {e}")


@register("rmdir", "Remove empty dir.")
def cmd_rmdir(args):
    if not args: print("[ERROR] Usage: rmdir <dir>"); return
    try:
        os.rmdir(resolve_path(args[0]))
        print(f"[ok] Removed {resolve_path(args[0])}")
    except Exception as e: print(f"[ERROR] {e}")


@register("find", "Find files.")
def cmd_find(args):
    if not args: print("[ERROR] Usage: find <name>"); return
    needle = args[0].lower(); hits = 0
    for root, dirs, files in os.walk(STATE["cwd"]):
        for f in files + dirs:
            if needle in f.lower():
                print(os.path.join(root, f)); hits += 1
                if hits >= 200: print("[...truncated]"); return
    if hits == 0: print("[no matches]")


@register("grep", "Search file.")
def cmd_grep(args):
    if len(args) < 2: print("[ERROR] Usage: grep <pat> <file>"); return
    p = resolve_path(args[1])
    if not os.path.isfile(p): print(f"[ERROR] File not found"); return
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if args[0] in line: print(f"{i}: {line.rstrip()}")
    except Exception as e: print(f"[ERROR] {e}")


@register("head", "First lines.")
def cmd_head(args):
    if not args: print("[ERROR] Usage: head <file> [n]"); return
    n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= n: break
                print(line.rstrip())
    except Exception as e: print(f"[ERROR] {e}")


@register("tail", "Last lines.")
def cmd_tail(args):
    if not args: print("[ERROR] Usage: tail <file> [n]"); return
    n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in lines[-n:]: print(line.rstrip())
    except Exception as e: print(f"[ERROR] {e}")


@register("wc", "Count lines/words/chars.")
def cmd_wc(args):
    if not args: print("[ERROR] Usage: wc <file>"); return
    p = resolve_path(args[0])
    if not os.path.isfile(p): print(f"[ERROR] File not found"); return
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f: data = f.read()
        print(f"  {data.count(chr(10))}  {len(data.split())}  {len(data)}  {p}")
    except Exception as e: print(f"[ERROR] {e}")


@register("df", "Disk usage.")
def cmd_df(args):
    print(run_shell("wmic logicaldisk get size,freespace,caption" if is_windows() else "df -h"))


@register("cp", "Copy file.")
def cmd_cp(args):
    if len(args) < 2: print("[ERROR] Usage: cp <src> <dst>"); return
    src = resolve_path(args[0]); dst = resolve_path(args[1])
    if not os.path.exists(src): print(f"[ERROR] Not found: {src}"); return
    try:
        if os.path.isdir(src): shutil.copytree(src, dst)
        else: shutil.copy2(src, dst)
        print(f"[ok] Copied")
    except Exception as e: print(f"[ERROR] {e}")


@register("mv", "Move/rename.")
def cmd_mv(args):
    if len(args) < 2: print("[ERROR] Usage: mv <src> <dst>"); return
    src = resolve_path(args[0]); dst = resolve_path(args[1])
    if not os.path.exists(src): print(f"[ERROR] Not found: {src}"); return
    try:
        shutil.move(src, dst); print(f"[ok] Moved")
    except Exception as e: print(f"[ERROR] {e}")


@register("touch", "Create empty file.")
def cmd_touch(args):
    if not args: print("[ERROR] Usage: touch <file>"); return
    try:
        with open(resolve_path(args[0]), "a", encoding="utf-8"): pass
        print(f"[ok] Touched")
    except Exception as e: print(f"[ERROR] {e}")


@register("write", "Write to file.")
def cmd_write(args):
    if len(args) < 2: print("[ERROR] Usage: write <file> <text...>"); return
    try:
        with open(resolve_path(args[0]), "w", encoding="utf-8") as f:
            f.write(" ".join(args[1:]) + "\n")
        print("[ok] Wrote")
    except Exception as e: print(f"[ERROR] {e}")


@register("append", "Append to file.")
def cmd_append(args):
    if len(args) < 2: print("[ERROR] Usage: append <file> <text...>"); return
    try:
        with open(resolve_path(args[0]), "a", encoding="utf-8") as f:
            f.write(" ".join(args[1:]) + "\n")
        print("[ok] Appended")
    except Exception as e: print(f"[ERROR] {e}")


@register("rename", "Rename file.")
def cmd_rename(args): cmd_mv(args)


@register("tree", "Directory tree.")
def cmd_tree(args):
    root = resolve_path(args[0]) if args else STATE["cwd"]
    max_depth = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
    if not os.path.isdir(root): print(f"[ERROR] Not a dir: {root}"); return
    def walk(path, prefix, depth):
        if depth > max_depth: return
        try: entries = sorted(os.listdir(path))
        except PermissionError: return
        for i, e in enumerate(entries):
            full = os.path.join(path, e)
            is_last = (i == len(entries) - 1)
            conn = "└── " if is_last else "├── "
            print(f"{prefix}{conn}{e}")
            if os.path.isdir(full):
                ext = "    " if is_last else "│   "
                walk(full, prefix + ext, depth + 1)
    print(root); walk(root, "", 1)


@register("size", "Size of path.")
def cmd_size(args):
    if not args: print("[ERROR] Usage: size <path>"); return
    p = resolve_path(args[0])
    if not os.path.exists(p): print(f"[ERROR] Not found"); return
    if os.path.isfile(p): print(f"{human_bytes(os.path.getsize(p))}  {p}"); return
    total = 0; count = 0
    for root, dirs, files in os.walk(p):
        for f in files:
            try: total += os.path.getsize(os.path.join(root, f)); count += 1
            except Exception: pass
    print(f"{human_bytes(total)}  {count} files  {p}")


# ============================================================
#  TEXT
# ============================================================
@register("sort", "Sort lines.")
def cmd_sort(args):
    if not args: print("[ERROR] Usage: sort <file>"); return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            for line in sorted(f): print(line.rstrip())
    except Exception as e: print(f"[ERROR] {e}")


@register("uniq", "Remove dupes.")
def cmd_uniq(args):
    if not args: print("[ERROR] Usage: uniq <file>"); return
    try:
        seen = set()
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line not in seen:
                    seen.add(line); print(line.rstrip())
    except Exception as e: print(f"[ERROR] {e}")


@register("rev", "Reverse each line.")
def cmd_rev(args):
    if not args: print("[ERROR] Usage: rev <file>"); return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            for line in f: print(line.rstrip()[::-1])
    except Exception as e: print(f"[ERROR] {e}")


@register("replace", "Replace text.")
def cmd_replace(args):
    if len(args) < 3: print("[ERROR] Usage: replace <file> <old> <new>"); return
    p = resolve_path(args[0])
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f: data = f.read()
        count = data.count(args[1]); data = data.replace(args[1], args[2])
        with open(p, "w", encoding="utf-8") as f: f.write(data)
        print(f"[ok] Replaced {count}")
    except Exception as e: print(f"[ERROR] {e}")


@register("lines", "Count lines.")
def cmd_lines(args):
    if not args: print("[ERROR] Usage: lines <file>"); return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            print(f"  {sum(1 for _ in f)} lines")
    except Exception as e: print(f"[ERROR] {e}")


@register("join", "Join lines.")
def cmd_join(args):
    if len(args) < 2: print("[ERROR] Usage: join <file> <sep>"); return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            print(args[1].join(l.rstrip("\n") for l in f))
    except Exception as e: print(f"[ERROR] {e}")


@register("split", "Split file.")
def cmd_split(args):
    if len(args) < 2: print("[ERROR] Usage: split <file> <n>"); return
    p = resolve_path(args[0])
    try:
        n = int(args[1])
        with open(p, "r", encoding="utf-8", errors="replace") as f: lines = f.readlines()
        base, ext = os.path.splitext(p)
        for i in range(0, len(lines), n):
            out = f"{base}_part{i//n + 1}{ext}"
            with open(out, "w", encoding="utf-8") as f: f.writelines(lines[i:i+n])
            print(f"  [ok] {out}")
    except Exception as e: print(f"[ERROR] {e}")


@register("upper", "Uppercase.")
def cmd_upper(args):
    if not args: print("[ERROR] Usage: upper <file>"); return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            print(f.read().upper())
    except Exception as e: print(f"[ERROR] {e}")


@register("lower", "Lowercase.")
def cmd_lower(args):
    if not args: print("[ERROR] Usage: lower <file>"); return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as f:
            print(f.read().lower())
    except Exception as e: print(f"[ERROR] {e}")


@register("swap", "Swap two files.")
def cmd_swap(args):
    if len(args) < 2: print("[ERROR] Usage: swap <f1> <f2>"); return
    a = resolve_path(args[0]); b = resolve_path(args[1])
    if not os.path.isfile(a) or not os.path.isfile(b): print("[ERROR] Both must exist."); return
    tmp = a + ".swaptmp"
    try:
        os.rename(a, tmp); os.rename(b, a); os.rename(tmp, b)
        print("[ok] Swapped")
    except Exception as e: print(f"[ERROR] {e}")


@register("diff", "Compare two files.")
def cmd_diff(args):
    if len(args) < 2: print("[ERROR] Usage: diff <f1> <f2>"); return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8", errors="replace") as a: l1 = a.readlines()
        with open(resolve_path(args[1]), "r", encoding="utf-8", errors="replace") as b: l2 = b.readlines()
        diffs = 0
        for i in range(max(len(l1), len(l2))):
            x = l1[i].rstrip("\n") if i < len(l1) else ""
            y = l2[i].rstrip("\n") if i < len(l2) else ""
            if x != y:
                print(f"  {i+1}:")
                print(f"    {RED}- {x}{RESET}")
                print(f"    {GREEN}+ {y}{RESET}")
                diffs += 1
        print(f"\n  {diffs} differing line(s)")
    except Exception as e: print(f"[ERROR] {e}")


# ============================================================
#  ARCHIVE / CLIPBOARD
# ============================================================
@register("zip", "Zip file.")
def cmd_zip(args):
    if not args: print("[ERROR] Usage: zip <src> [out.zip]"); return
    src = resolve_path(args[0])
    if not os.path.exists(src): print(f"[ERROR] Not found"); return
    out = resolve_path(args[1]) if len(args) > 1 else os.path.join(STATE["cwd"], os.path.basename(src.rstrip("/\\")) + ".zip")
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(src): zf.write(src, os.path.basename(src))
            else:
                for root, dirs, files in os.walk(src):
                    for f in files:
                        full = os.path.join(root, f)
                        zf.write(full, os.path.relpath(full, os.path.dirname(src)))
        print(f"[ok] Zipped -> {out}")
    except Exception as e: print(f"[ERROR] {e}")


@register("unzip", "Extract zip.")
def cmd_unzip(args):
    if not args: print("[ERROR] Usage: unzip <file.zip> [dest]"); return
    src = resolve_path(args[0])
    dest = resolve_path(args[1]) if len(args) > 1 else os.path.splitext(src)[0]
    try:
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(src, "r") as zf: zf.extractall(dest)
        print(f"[ok] Extracted -> {dest}")
    except Exception as e: print(f"[ERROR] {e}")


@register("tar", "Create tar.gz.")
def cmd_tar(args):
    if not args: print("[ERROR] Usage: tar <src> [out.tar.gz]"); return
    src = resolve_path(args[0])
    out = resolve_path(args[1]) if len(args) > 1 else os.path.join(STATE["cwd"], os.path.basename(src.rstrip("/\\")) + ".tar.gz")
    try:
        with tarfile.open(out, "w:gz") as tf: tf.add(src, arcname=os.path.basename(src.rstrip("/\\")))
        print(f"[ok] Tarball -> {out}")
    except Exception as e: print(f"[ERROR] {e}")


@register("untar", "Extract tar.gz.")
def cmd_untar(args):
    if not args: print("[ERROR] Usage: untar <file.tar.gz> [dest]"); return
    dest = resolve_path(args[1]) if len(args) > 1 else STATE["cwd"]
    try:
        with tarfile.open(resolve_path(args[0]), "r:gz") as tf: tf.extractall(dest)
        print(f"[ok] Extracted -> {dest}")
    except Exception as e: print(f"[ERROR] {e}")


@register("clip", "Copy to clipboard.")
def cmd_clip(args):
    if not args: print("[ERROR] Usage: clip <file>"); return
    p = resolve_path(args[0])
    if not os.path.isfile(p): print(f"[ERROR] File not found"); return
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f: data = f.read()
        if is_windows(): subprocess.run("clip", input=data, text=True, shell=True)
        elif is_android(): subprocess.run("termux-clipboard-set", input=data, text=True, shell=True)
        else: print("[ERROR] Windows/Android only."); return
        print(f"[ok] Copied {len(data)} chars")
    except Exception as e: print(f"[ERROR] {e}")


@register("paste", "Show clipboard.")
def cmd_paste(args):
    if is_windows(): out = _safe_run("powershell Get-Clipboard", timeout=10)
    elif is_android(): out = _safe_run("termux-clipboard-get", timeout=10)
    else: print("[ERROR] Windows/Android only."); return
    print(out if out.strip() else "[empty clipboard]")


# ============================================================
#  SYSTEM
# ============================================================
@register("echo", "Print text.")
def cmd_echo(args): print(" ".join(args))


@register("whoami", "Current user.")
def cmd_whoami(args): print(STATE["user"])


@register("sysinfo", "Hardware specs.")
def cmd_sysinfo(args):
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
        if specs.get("mobo_vendor"): mobo = f"{specs['mobo_vendor']} {mobo}"
        print(f"  Motherboard: {mobo}")
    cpu = specs.get("cpu_name", platform.processor() or "?")
    extras = []
    if specs.get("cpu_cores"): extras.append(f"{specs['cpu_cores']} cores")
    if specs.get("cpu_threads"): extras.append(f"{specs['cpu_threads']} threads")
    if specs.get("cpu_mhz"):
        try: extras.append(f"{float(specs['cpu_mhz'])/1000:.2f} GHz")
        except ValueError: pass
    print(f"  CPU        : {cpu} ({', '.join(extras)})" if extras else f"  CPU        : {cpu}")
    if specs.get("ram_bytes"): print(f"  RAM        : {human_bytes(specs['ram_bytes'])}")
    if specs.get("gpus"):
        for i, g in enumerate(specs["gpus"]):
            label = "GPU" if i == 0 else "           "
            name = g.get("name", "?"); vram = g.get("vram")
            if vram and vram > 0: print(f"  {label}        : {name} ({human_bytes(vram)} VRAM)")
            else: print(f"  {label}        : {name}")
    if specs.get("disks"):
        print(f"  Disks      :")
        for d in specs["disks"]: print(f"               - {d}")
    print()


@register("os", "OS info.")
def cmd_os(args):
    print_header("Operating System")
    print(f"  System  : {platform.system()}")
    print(f"  Release : {platform.release()}")
    print(f"  Version : {platform.version()}")
    print(f"  Arch    : {platform.machine()}")
    print(f"  Node    : {platform.node()}")
    print()


@register("cpu", "CPU info.")
def cmd_cpu(args):
    print(run_shell("wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed /format:list" if is_windows() else "cat /proc/cpuinfo | head -30"))


@register("mem", "Memory.")
def cmd_mem(args):
    print(run_shell("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /format:list" if is_windows() else "free -h"))


@register("gpu", "GPU info.")
def cmd_gpu(args):
    print(run_shell("wmic path win32_VideoController get Name /format:list" if is_windows() else "lspci | grep -i vga"))


@register("hostname", "Show/set hostname.")
def cmd_hostname(args):
    if args:
        STATE["host"] = args[0]; print(f"[host] -> {args[0]}")
    else: print(platform.node())


@register("user", "Current user.")
def cmd_user(args): print(STATE["user"])


@register("env", "Environment vars.")
def cmd_env(args):
    if args: print(os.environ.get(args[0], f"[not set] {args[0]}")); return
    for k, v in sorted(os.environ.items()): print(f"  {k}={v}")


@register("time", "Time.")
def cmd_time(args): print(time.strftime("%Y-%m-%d %H:%M:%S"))


@register("date", "Date.")
def cmd_date(args): print(time.strftime("%Y-%m-%d"))


@register("uptime", "Uptime.")
def cmd_uptime(args):
    if is_windows():
        try:
            import ctypes
            tick_count = ctypes.windll.kernel32.GetTickCount64()
            uptime_ms = tick_count
            hours = uptime_ms // (1000 * 60 * 60)
            minutes = (uptime_ms % (1000 * 60 * 60)) // (1000 * 60)
            print(f"  System Uptime: {hours}h {minutes}m")
        except Exception as e:
            print(f"[ERROR] {e}")
    else:
        print(run_shell("uptime"))


@register("temp", "Temp files.")
def cmd_temp(args):
    tmpdir = tempfile.gettempdir()
    if args and args[0].lower() == "clear":
        count = 0
        for f in os.listdir(tmpdir):
            try:
                full = os.path.join(tmpdir, f)
                if os.path.isfile(full): os.remove(full); count += 1
                elif os.path.isdir(full): shutil.rmtree(full, ignore_errors=True); count += 1
            except Exception: pass
        print(f"[ok] Cleared {count} item(s)")
        return
    files = os.listdir(tmpdir); total = 0
    for f in files:
        try: total += os.path.getsize(os.path.join(tmpdir, f))
        except Exception: pass
    print(f"  Temp: {tmpdir}")
    print(f"  Files: {len(files)}")
    print(f"  Size : {human_bytes(total)}")


@register("proc", "Process count.")
def cmd_proc(args): print(f"  Running processes: {len(get_processes())}")


@register("top5", "Top 5 processes.")
def cmd_top5(args): cmd_top(["5"])


@register("services", "Services (Win).")
def cmd_services(args):
    if not is_windows(): print("[ERROR] Windows only."); return
    print(run_shell("sc query type= service state= all | findstr SERVICE_NAME"))


@register("startup", "Startup programs (Win).")
def cmd_startup(args):
    if not is_windows(): print("[ERROR] Windows only."); return
    print(run_shell("wmic startup get Caption,Command"))


@register("drivers", "Drivers (Win).")
def cmd_drivers(args):
    if not is_windows(): print("[ERROR] Windows only."); return
    print(run_shell("driverquery"))


# ============================================================
#  DEV
# ============================================================
@register("py", "Run Python file.")
def cmd_py(args):
    if not args: print("[ERROR] Usage: py <file.py> [args...]"); return
    p = resolve_path(args[0])
    if not os.path.isfile(p): print(f"[ERROR] File not found: {p}"); return
    run_shell(f'python "{p}" ' + " ".join(args[1:]), live=True, timeout=300)


@register("json", "Pretty JSON.")
def cmd_json(args):
    if not args: print("[ERROR] Usage: json <file>"); return
    try:
        with open(resolve_path(args[0]), "r", encoding="utf-8") as f:
            print(json.dumps(json.load(f), indent=2))
    except Exception as e: print(f"[ERROR] {e}")


@register("hex", "Hex dump.")
def cmd_hex(args):
    if not args: print("[ERROR] Usage: hex <file> [n]"); return
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 256
    try:
        with open(resolve_path(args[0]), "rb") as f: data = f.read(limit)
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            h = " ".join(f"{b:02x}" for b in chunk)
            a = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"  {i:08x}  {h:<48}  {a}")
    except Exception as e: print(f"[ERROR] {e}")


@register("count", "Count files by ext.")
def cmd_count(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    ext_count = {}
    for root, dirs, files in os.walk(path):
        for f in files:
            ext = os.path.splitext(f)[1].lower() or "(none)"
            ext_count[ext] = ext_count.get(ext, 0) + 1
    for ext, n in sorted(ext_count.items(), key=lambda x: x[1], reverse=True)[:30]:
        print(f"  {n:>6}  {ext}")


@register("todo", "Find TODOs.")
def cmd_todo(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for f in files:
            if not f.endswith((".py", ".js", ".ts", ".md", ".txt")): continue
            full = os.path.join(root, f)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if "TODO" in line.upper() or "FIXME" in line.upper():
                            print(f"  {full}:{i}  {line.strip()[:80]}"); count += 1
            except Exception: pass
    print(f"\n  {count} match(es)")


# ============================================================
#  BATCH
# ============================================================
@register("findext", "Find by extension.")
def cmd_findext(args):
    if not args: print("[ERROR] Usage: findext <ext>"); return
    ext = args[0]
    if not ext.startswith("."): ext = "." + ext
    hits = 0
    for root, dirs, files in os.walk(STATE["cwd"]):
        for f in files:
            if f.lower().endswith(ext.lower()):
                print(os.path.join(root, f)); hits += 1
                if hits >= 300: print("[...truncated]"); return
    if hits == 0: print(f"[no {ext} files]")


@register("empty", "Empty files.")
def cmd_empty(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    count = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            full = os.path.join(root, f)
            try:
                if os.path.getsize(full) == 0: print(f"  {full}"); count += 1
            except Exception: pass
    print(f"\n  {count} empty file(s)")


@register("bigfiles", "Biggest files.")
def cmd_bigfiles(args):
    n = int(args[0]) if args and args[0].isdigit() else 15
    files = []
    for root, dirs, fs in os.walk(STATE["cwd"]):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for f in fs:
            full = os.path.join(root, f)
            try: files.append((os.path.getsize(full), full))
            except Exception: pass
    files.sort(reverse=True)
    print_header(f"Top {n} biggest files")
    for size, path in files[:n]: print(f"  {human_bytes(size):>10}  {path}")
    print()


# ============================================================
#  UTILITY
# ============================================================
@register("calc", "Calculate.")
def cmd_calc(args):
    if not args: print("[ERROR] Usage: calc <expr>"); return
    try: print(f"  {eval(' '.join(args), {'__builtins__': {}}, {})}")
    except Exception as e: print(f"[ERROR] {e}")


@register("random", "Random number.")
def cmd_random(args):
    lo = int(args[0]) if args and args[0].lstrip("-").isdigit() else 1
    hi = int(args[1]) if len(args) > 1 and args[1].lstrip("-").isdigit() else 100
    print(f"  {random.randint(lo, hi)}")


@register("uuid", "UUID.")
def cmd_uuid(args):
    import uuid as _u; print(f"  {_u.uuid4()}")


@register("hash", "Hash string.")
def cmd_hash(args):
    if len(args) < 2: print("[ERROR] Usage: hash <algo> <text>"); return
    algo = args[0].lower()
    if algo not in ("md5", "sha1", "sha256", "sha512"): print("[ERROR] md5/sha1/sha256/sha512"); return
    print(f"  {hashlib.new(algo, ' '.join(args[1:]).encode()).hexdigest()}")


@register("base64", "Base64.")
def cmd_base64(args):
    if not args: print("[ERROR] Usage: base64 [-d] <text>"); return
    decode = args[0] == "-d"
    text = " ".join(args[1:] if decode else args)
    try:
        if decode: print(f"  {_b64.b64decode(text.encode()).decode()}")
        else: print(f"  {_b64.b64encode(text.encode()).decode()}")
    except Exception as e: print(f"[ERROR] {e}")


@register("now", "Datetime.")
def cmd_now(args): print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@register("stopwatch", "Stopwatch.")
def cmd_stopwatch(args):
    print("[stopwatch] Press Enter to stop...")
    start = time.time()
    try: input()
    except (EOFError, KeyboardInterrupt): pass
    print(f"  Elapsed: {time.time() - start:.2f} seconds")


@register("password", "Generate password.")
def cmd_password(args):
    length = int(args[0]) if args and args[0].isdigit() else 16
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    print(f"  {''.join(random.choice(chars) for _ in range(length))}")


@register("unitconvert", "Convert units.")
def cmd_unitconvert(args):
    if len(args) < 3: print("[ERROR] Usage: unitconvert <v> <from> <to>"); return
    try: val = float(args[0])
    except ValueError: print("[ERROR] v must be number."); return
    fr, to = args[1].lower(), args[2].lower()
    def tf(v):
        if fr == "c": return v + 273.15
        if fr == "f": return (v + 459.67) * 5/9
        if fr == "k": return v
    def tfrom(k):
        if to == "c": return k - 273.15
        if to == "f": return k * 9/5 - 459.67
        if to == "k": return k
    if fr in ("c","f","k") and to in ("c","f","k"):
        print(f"  {val}{fr} = {tfrom(tf(val)):.2f}{to}"); return
    lengths = {"m":1,"km":1000,"mi":1609.344,"ft":0.3048,"cm":0.01}
    if fr in lengths and to in lengths:
        print(f"  {val}{fr} = {val * lengths[fr] / lengths[to]:.4f}{to}"); return
    mass = {"kg":1,"g":0.001,"lb":0.453592,"oz":0.0283495}
    if fr in mass and to in mass:
        print(f"  {val}{fr} = {val * mass[fr] / mass[to]:.4f}{to}"); return
    print("[ERROR] Unsupported.")


@register("bmi", "BMI.")
def cmd_bmi(args):
    if len(args) < 2: print("[ERROR] Usage: bmi <kg> <cm>"); return
    try:
        kg, cm = float(args[0]), float(args[1])
        b = kg / ((cm/100) ** 2)
        cat = "Underweight" if b < 18.5 else "Normal" if b < 25 else "Overweight" if b < 30 else "Obese"
        print(f"  BMI: {b:.1f}  ({cat})")
    except Exception as e: print(f"[ERROR] {e}")


@register("avg", "Average.")
def cmd_avg(args):
    try: nums = [float(a) for a in args]
    except ValueError: print("[ERROR] All numbers."); return
    if not nums: print("[ERROR] Need numbers."); return
    print(f"  Sum: {sum(nums)}  Avg: {sum(nums)/len(nums):.4f}")
    print(f"  Min: {min(nums)}  Max: {max(nums)}")


@register("prime", "Is prime.")
def cmd_prime(args):
    if not args: print("[ERROR] Usage: prime <n>"); return
    try: n = int(args[0])
    except ValueError: print("[ERROR] integer needed."); return
    if n < 2: print(f"  {n} not prime."); return
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0: print(f"  {n} not prime (÷{i})"); return
    print(f"  {n} is prime.")


@register("factors", "Factors.")
def cmd_factors(args):
    if not args: print("[ERROR] Usage: factors <n>"); return
    try: n = abs(int(args[0]))
    except ValueError: print("[ERROR] integer needed."); return
    print(f"  {n}: {[i for i in range(1, n+1) if n % i == 0]}")


@register("timer", "Countdown.")
def cmd_timer(args):
    if not args: print("[ERROR] Usage: timer <seconds>"); return
    try:
        n = int(args[0])
        for i in range(n, 0, -1):
            print(f"  {i}..."); time.sleep(1)
        print("  [DONE]"); print("\a", end="", flush=True)
    except (ValueError, KeyboardInterrupt): print("  [cancelled]")


@register("morse", "Text to Morse.")
def cmd_morse(args):
    if not args: print("[ERROR] Usage: morse <text>"); return
    code = {"A":".-","B":"-...","C":"-.-.","D":"-..","E":".","F":"..-.","G":"--.","H":"....",
            "I":"..","J":".---","K":"-.-","L":".-..","M":"--","N":"-.","O":"---","P":".--.",
            "Q":"--.-","R":".-.","S":"...","T":"-","U":"..-","V":"...-","W":".--","X":"-..-",
            "Y":"-.--","Z":"--..","0":"-----","1":".----","2":"..---","3":"...--","4":"....-",
            "5":".....","6":"-....","7":"--...","8":"---..","9":"----."," ":"/"}
    print("  " + " ".join(code.get(c, "?") for c in " ".join(args).upper()))


@register("caesar", "Caesar cipher.")
def cmd_caesar(args):
    if len(args) < 2: print("[ERROR] Usage: caesar <shift> <text>"); return
    try: shift = int(args[0])
    except ValueError: print("[ERROR] shift must be number."); return
    out = ""
    for c in " ".join(args[1:]):
        if c.isalpha():
            base = ord("A") if c.isupper() else ord("a")
            out += chr((ord(c) - base + shift) % 26 + base)
        else: out += c
    print(f"  {out}")


@register("roll", "Roll dice.")
def cmd_roll(args):
    if not args or "d" not in args[0]: print("[ERROR] Usage: roll <n>d<sides>"); return
    try:
        n, s = args[0].lower().split("d")
        n = int(n) if n else 1
        s = int(s)
    except ValueError: print("[ERROR] Invalid format."); return
    rolls = [random.randint(1, s) for _ in range(n)]
    print(f"  Rolls: {rolls}")
    print(f"  Total: {sum(rolls)}")


@register("rps", "Rock paper scissors.")
def cmd_rps(args):
    if not args or args[0].lower() not in ("rock","paper","scissors"): print("[ERROR] Usage: rps <rock|paper|scissors>"); return
    player = args[0].lower()
    comp = random.choice(["rock","paper","scissors"])
    print(f"  You: {player}  Computer: {comp}")
    if player == comp: print("  Draw!")
    elif (player == "rock" and comp == "scissors") or (player == "paper" and comp == "rock") or (player == "scissors" and comp == "paper"): print("  You win!")
    else: print("  Computer wins.")


@register("luck", "Luck %.")
def cmd_luck(args):
    pct = random.randint(0, 100)
    bar = "#" * (pct // 5) + "." * (20 - pct // 5)
    print(f"  Luck: {pct}%  [{bar}]")


@register("coin", "Flip coin.")
def cmd_coin(args): print(f"  {'HEADS' if random.randint(0, 1) == 0 else 'TAILS'}")


@register("dice", "Roll die.")
def cmd_dice(args):
    sides = int(args[0]) if args and args[0].isdigit() else 6
    print(f"  {random.randint(1, sides)}")


@register("shuffle", "Shuffle.")
def cmd_shuffle(args):
    if not args: print("[ERROR] Usage: shuffle <a> <b> ..."); return
    items = list(args); random.shuffle(items); print(f"  {' '.join(items)}")


@register("pick", "Pick one.")
def cmd_pick(args):
    if not args: print("[ERROR] Usage: pick <a> <b> ..."); return
    print(f"  {random.choice(args)}")


@register("fortune", "Fortune.")
def cmd_fortune(args):
    fs = ["You will write a bug that haunts you for years.",
          "The bug is not in the code. It's in the assumptions.",
          "Take the nap. It's the answer.",
          "You will be productive tomorrow.",
          "Someone is thinking about you right now.",
          "A stranger will compliment your work.",
          "The stack overflow is on line 42.",
          "Someone out there loves you. Probably more than one."]
    print(f"  {random.choice(fs)}")


@register("quote", "Quote.")
def cmd_quote(args):
    qs = [("Talk is cheap. Show me the code.", "Linus Torvalds"),
          ("Premature optimization is the root of all evil.", "Donald Knuth"),
          ("Code is like humor. When you have to explain it, it's bad.", "Cory House"),
          ("Simplicity is the soul of efficiency.", "Austin Freeman"),
          ("First, solve the problem. Then write the code.", "John Johnson")]
    q, a = random.choice(qs)
    print(f"  \"{q}\"")
    print(f"      - {a}")


@register("challenge", "Coding challenge.")
def cmd_challenge(args):
    cs = ["Return the nth Fibonacci in O(1) space.",
          "Reverse a linked list without extra memory.",
          "Find longest palindromic substring.",
          "Stack that returns minimum in O(1).",
          "Merge two sorted arrays in-place.",
          "Detect a cycle in a linked list."]
    print(f"  {random.choice(cs)}")


@register("cowsay", "Cow says something.")
def cmd_cowsay(args):
    text = " ".join(args) if args else "Hello from Eclipse Shell!"
    b = "-" * (len(text) + 2)
    print(f"  {b}"); print(f"  {text}"); print(f"  {b}")
    print("        \\   ^__^")
    print("         \\  (oo)\\_______")
    print("            (__)\\       )\\/\\")
    print("                ||----w |")
    print("                ||     ||")


@register("matrix", "Matrix rain.")
def cmd_matrix(args):
    try:
        for _ in range(20):
            print("  " + "".join(random.choice("01 ") for _ in range(60)))
            time.sleep(0.05)
    except KeyboardInterrupt: pass


@register("meme", "Random meme.")
def cmd_meme(args):
    ms = ["you got this", "ship it", "one more bug and then sleep",
          "it works on my machine", "delete node_modules and try again",
          "have you tried turning it off and on again",
          "80% done, 80% to go", "git commit -m 'fixed stuff'",
          "code is poetry. broken poetry."]
    print(f"  {random.choice(ms)}")


@register("progressbar", "Progress bar.")
def cmd_progressbar(args):
    secs = float(args[0]) if args and args[0].replace(".","").isdigit() else 3.0
    for i in range(21):
        fill = i * 2
        bar = "#" * fill + "." * (40 - fill)
        sys.stdout.write(f"\r  [{bar}] {i*5:3d}%")
        sys.stdout.flush()
        time.sleep(secs / 20)
    print()


@register("spinner", "Spinner.")
def cmd_spinner(args):
    secs = float(args[0]) if args and args[0].replace(".","").isdigit() else 3.0
    frames = ["|", "/", "-", "\\"]
    end = time.time() + secs
    i = 0
    while time.time() < end:
        sys.stdout.write(f"\r  {frames[i % 4]} working...")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    print("\r  done.       ")


@register("beep", "Beep.  Usage: beep [freq] [ms]")
def cmd_beep(args):
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


@register("calendar", "Calendar.")
def cmd_calendar(args):
    import calendar as c
    n = datetime.datetime.now()
    c.prmonth(n.year, n.month)


@register("timestamp", "Unix timestamp.")
def cmd_timestamp(args): print(f"  {int(time.time())}")


@register("daysuntil", "Days until.")
def cmd_daysuntil(args):
    if not args: print("[ERROR] Usage: daysuntil YYYY-MM-DD"); return
    try:
        t = datetime.datetime.strptime(args[0], "%Y-%m-%d")
        print(f"  {(t - datetime.datetime.now()).days} day(s)")
    except Exception as e: print(f"[ERROR] {e}")


# ============================================================
#  PROCESS
# ============================================================
@register("tasklist", "Processes.")
def cmd_tasklist(args):
    procs = get_processes()
    if args: procs = [p for p in procs if args[0].lower() in p["name"].lower()]
    if not procs: print("[no processes]"); return
    procs.sort(key=lambda p: p["mem_kb"], reverse=True)
    print_header(f"Processes - {len(procs)}")
    print(f"  {'PID':>7}  {'MEM':>10}  NAME")
    for p in procs: print(f"  {p['pid']:>7}  {human_kb(p['mem_kb']):>10}  {p['name']}")
    print()


@register("ps", "Processes (alias).")
def cmd_ps(args): cmd_tasklist(args)


@register("top", "Top processes.")
def cmd_top(args):
    n = int(args[0]) if args and args[0].isdigit() else 15
    procs = get_processes()
    procs.sort(key=lambda p: p["mem_kb"], reverse=True)
    print_header(f"Top {n}")
    for p in procs[:n]: print(f"  {p['pid']:>7}  {human_kb(p['mem_kb']):>10}  {p['name']}")
    print()


@register("taskinfo", "Process details.")
def cmd_taskinfo(args):
    if not args: print("[ERROR] Usage: taskinfo <pid|name>"); return
    procs = get_processes(); t = args[0]
    matches = [p for p in procs if p["pid"] == int(t)] if t.isdigit() else [p for p in procs if t.lower() in p["name"].lower()]
    if not matches: print(f"[ERROR] No process: {t}"); return
    for p in matches:
        print_header(f"Process: {p['name']}")
        print(f"  PID    : {p['pid']}")
        print(f"  Memory : {human_kb(p['mem_kb'])}")
        print(f"  User   : {p['user'] or '(unknown)'}")
        print()


@register("kill", "Kill process.")
def cmd_kill(args):
    if not args: print("[ERROR] Usage: kill <pid>"); return
    cmd = f"taskkill /PID {args[0]} /F" if is_windows() else f"kill -9 {args[0]}"
    print(run_shell(cmd))


@register("battery", "Battery.")
def cmd_battery(args):
    if is_android(): print(run_shell("termux-battery-status"))
    elif is_windows(): print(run_shell("WMIC Path Win32_Battery Get EstimatedChargeRemaining"))
    else: print(run_shell("upower -i $(upower -e | grep BAT)"))


@register("storage", "Storage.")
def cmd_storage(args):
    print(run_shell("wmic logicaldisk get size,freespace,caption" if is_windows() else "df -h"))


@register("apps", "Android apps.")
def cmd_apps(args):
    if not is_android(): print("[ERROR] Android only."); return
    print(run_shell("pm list packages | head -50"))


# ============================================================
#  START
# ============================================================
@register("start", "Launch program.")
def cmd_start(args):
    if not args: print("[ERROR] Usage: start <program> [args...]"); return
    path = find_program(args[0])
    if not path: print(f"[ERROR] Not found: {args[0]}"); return
    try:
        if is_windows(): subprocess.Popen(f'start "" "{path}" ' + " ".join(args[1:]), shell=True)
        else: subprocess.Popen([path] + args[1:], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        print(f"[start] Launched: {path}")
    except Exception as e: print(f"[ERROR] {e}")


# ============================================================
#  NETWORK
# ============================================================
@register("wlan", "WiFi profiles.")
def cmd_wlan(args):
    if is_windows():
        if args and args[0].lower() == "profile" and len(args) >= 2:
            print(run_shell(f'netsh wlan show profile name="{args[1]}" key=clear', timeout=30))
        else: print(run_shell("netsh wlan show profile", timeout=30))
    elif is_android(): print(run_shell("dumpsys wifi | grep -i ssid"))
    else: print("[ERROR] Windows/Android only.")


@register("ping", "Ping host.")
def cmd_ping(args):
    if not args: print("[ERROR] Usage: ping <host> [count]"); return
    count = args[1] if len(args) > 1 else "4"
    flag = "-n" if is_windows() else "-c"
    run_shell(f"ping {flag} {count} {args[0]}", live=True)


@register("ip", "IP config.")
def cmd_ip(args): print(run_shell("ipconfig" if is_windows() else "ip addr || ifconfig"))


@register("ifconfig", "Interfaces.")
def cmd_ifconfig(args): cmd_ip(args)


@register("netstat", "Connections.")
def cmd_netstat(args): print(run_shell("netstat -an"))


@register("route", "Routing table.")
def cmd_route(args): print(run_shell("route print" if is_windows() else "ip route || route -n"))


@register("arp", "ARP table.")
def cmd_arp(args): print(run_shell("arp -a"))


@register("nslookup", "DNS lookup.")
def cmd_nslookup(args):
    if not args: print("[ERROR] Usage: nslookup <host>"); return
    print(run_shell(f"nslookup {args[0]}"))


@register("tracert", "Trace route.")
def cmd_tracert(args):
    if not args: print("[ERROR] Usage: tracert <host>"); return
    print(f"[tracert] tracing {args[0]}..."); sys.stdout.flush()
    cmd = f"tracert -d -w 1000 -h 15 {args[0]}" if is_windows() else f"traceroute -n -w 1 -m 15 {args[0]}"
    try: subprocess.run(cmd, shell=True, timeout=90)
    except subprocess.TimeoutExpired: print("\n[tracert] timed out")
    except KeyboardInterrupt: print("\n[tracert] cancelled")


@register("localip", "Local IP.")
def cmd_localip(args):
    import socket as s
    try:
        sock = s.socket(s.AF_INET, s.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        print(f"  {sock.getsockname()[0]}"); sock.close()
    except Exception as e: print(f"[ERROR] {e}")


@register("publicip", "Public IP.")
def cmd_publicip(args): print(run_shell("curl -s https://api.ipify.org", timeout=15))


@register("port", "Check port.")
def cmd_port(args):
    if len(args) < 2: print("[ERROR] Usage: port <host> <port>"); return
    import socket as s
    try: p = int(args[1])
    except ValueError: print("[ERROR] Port must be number."); return
    sock = s.socket(s.AF_INET, s.SOCK_STREAM); sock.settimeout(3)
    try:
        r = sock.connect_ex((args[0], p))
        print(f"[{'open' if r == 0 else 'closed'}] {args[0]}:{p}")
    except Exception as e: print(f"[ERROR] {e}")
    finally: sock.close()


@register("curl", "Fetch URL.")
def cmd_curl(args):
    if not args: print("[ERROR] Usage: curl <url>"); return
    print(run_shell(f"curl -s {args[0]}", timeout=30))


@register("wget", "Download.")
def cmd_wget(args):
    if not args: print("[ERROR] Usage: wget <url>"); return
    if is_windows(): print("[ERROR] wget not on Windows."); return
    print(run_shell(f"wget -qO- {args[0]}", timeout=30))


# ============================================================
#  USER / POWER
# ============================================================
@register("cu", "Change username.")
def cmd_cu(args):
    if not args: print("[ERROR] Usage: cu <new_username>"); return
    old = STATE["user"]; STATE["user"] = args[0]
    print(f"[user] '{old}' -> '{args[0]}'")


@register("shutdown", "Shutdown PC.")
def cmd_shutdown(args):
    if is_windows():
        if not args: subprocess.run("shutdown /s /t 0", shell=True); return
        mode = args[0].lower(); secs = args[1] if len(args) > 1 else "0"
        if mode in ("s", "shutdown"): subprocess.run(f"shutdown /s /t {secs}", shell=True)
        elif mode in ("r", "restart", "reboot"): subprocess.run(f"shutdown /r /t {secs}", shell=True)
        elif mode in ("a", "abort"): subprocess.run("shutdown /a", shell=True)
        else: print("[ERROR] Usage: shutdown [s|r|a] [seconds]")
    elif is_android(): print(run_shell("su -c 'reboot -p' || echo '[ERROR] root required'"))
    else: print("[ERROR] Windows/Android only.")


@register("reboot", "Restart.")
def cmd_reboot(args):
    if is_windows(): subprocess.run("shutdown /r /t 0", shell=True)
    elif is_android(): print(run_shell("su -c 'reboot' || echo '[ERROR] root required'"))
    else: print("[ERROR] Windows/Android only.")


# ============================================================
#  CALL
# ============================================================
@register("call", "Call another command.")
def cmd_call(args):
    if not args: print("[ERROR] Usage: call <command> [args...]"); return
    name = args[0].lower().rstrip("()")
    if name == "call": print("[ERROR] 'call' cannot call itself."); return
    target = COMMANDS.get(name)
    if not target: print(f"[ERROR] '{name}' not registered."); return
    try: target["fn"](args[1:])
    except SystemExit: raise
    except Exception as e: print(f"[ERROR] {e}")


# ============================================================
#  PIPE + REDIRECT
# ============================================================
def run_pipeline(line):
    segments = [s.strip() for s in line.split("|") if s.strip()]
    stdin = None
    for i, seg in enumerate(segments):
        parts = seg.split()
        if not parts: continue
        name = parts[0].lower().rstrip("()")
        args = parts[1:]
        target = COMMANDS.get(name)
        if not target: print(f"[ERROR] Unknown: {name}"); return
        is_last = (i == len(segments) - 1)
        if stdin is not None and name == "grep" and len(args) == 1:
            filt = "\n".join(l for l in stdin.splitlines() if args[0] in l)
            stdin = filt
            if is_last: print(filt)
            continue
        buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
        try: target["fn"](args)
        except SystemExit: raise
        except Exception as e:
            sys.stdout = old; print(f"[ERROR] {e}"); return
        finally: sys.stdout = old
        out = buf.getvalue()
        if is_last: print(out, end="" if out.endswith("\n") else "\n")
        else: stdin = out


def run_redirect(line):
    if ">>" in line: left, right = line.split(">>", 1); append = True
    elif ">" in line: left, right = line.split(">", 1); append = False
    else: return False
    left = left.strip(); right = right.strip().strip('"').strip("'")
    if not left or not right: print("[ERROR] Missing command or file."); return True
    target = resolve_path(right)
    buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
    try: dispatch(left)
    except SystemExit: raise
    except Exception as e:
        sys.stdout = old; print(f"[ERROR] {e}"); return True
    finally: sys.stdout = old
    out = buf.getvalue()
    try:
        with open(target, "a" if append else "w", encoding="utf-8") as f: f.write(out)
        print(f"[redirect] {'Appended' if append else 'Wrote'} to {target}")
    except Exception as e: print(f"[ERROR] {e}")
    return True


# ============================================================
#  TAB COMPLETION
# ============================================================
def completer(text, state):
    if readline is None:
        return None
    options = [c for c in COMMANDS.keys() if c.startswith(text)]
    options += [a for a in STATE["aliases"].keys() if a.startswith(text)]
    if state < len(options):
        return options[state]
    return None


# ============================================================
#  DISPATCH
# ============================================================
def dispatch(line):
    parts = line.strip().split()
    if not parts: return

    # Check for aliases first
    first = parts[0]
    if first in STATE["aliases"]:
        line = STATE["aliases"][first] + " " + " ".join(parts[1:])
        parts = line.strip().split()
        if not parts: return

    STATE["history"].append(line.strip())
    name = parts[0].lower().rstrip("()")
    args = parts[1:]
    cmd = COMMANDS.get(name)
    if not cmd:
        print(f"[ERROR] Unknown command: {name}   (type 'help')")
        return
    try: cmd["fn"](args)
    except SystemExit: raise
    except Exception as e: print(f"[ERROR] {e}")


# ============================================================
#  BANNER
# ============================================================
def banner():
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
    print(f"  {len(COMMANDS)} commands registered.")
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
            if ">" in line: run_redirect(line)
            elif "|" in line: run_pipeline(line)
            else: dispatch(line)
        except SystemExit:
            break


if __name__ == "__main__":
    main()
