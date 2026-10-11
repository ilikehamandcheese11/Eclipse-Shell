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

# ============================================================
#  STATE
# ============================================================
STATE = {
    "cwd": os.getcwd(),
    "user": "eclipse",
    "host": "eclipse",
    "history": [],
    "version": "0.3.1",
    "status": "indev",
    "author": "ilikehamandcheese11",
    "youtube": "https://www.youtube.com/@ilikehamandcheese11",
    "discord": "@ilikehamandcheese11",
}

COMMANDS = {}


def register(name, desc=""):
    def wrapper(fn):
        COMMANDS[name] = {"fn": fn, "desc": desc or fn.__doc__ or ""}
        return fn
    return wrapper


# ============================================================
#  PLATFORM DETECTION
# ============================================================
def is_windows():
    return platform.system() == "Windows"


def is_android():
    if "com.termux" in os.environ.get("PREFIX", ""):
        return True
    if "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
        return True
    return False


def is_linux():
    return platform.system() == "Linux"


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
    """Run a shell command safely with UTF-8 decoding and error recovery."""
    try:
        if live:
            subprocess.run(cmd, shell=True)
            return ""
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = result.stdout or ""
        if result.stderr:
            out += "\n[stderr]\n" + result.stderr
        return out if out.strip() else "[no output]"
    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out."
    except Exception as e:
        return f"[ERROR] {e}"


# ============================================================
#  REAL PROCESS LISTING
# ============================================================
def get_processes():
    procs = []
    try:
        if is_windows():
            out = subprocess.run(
                'tasklist /FO CSV /NH',
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            ).stdout or ""
            reader = csv.reader(io.StringIO(out))
            for row in reader:
                if len(row) >= 5:
                    name = row[0]
                    pid = row[1]
                    mem = row[4].replace(",", "").replace(" K", "").strip()
                    try:
                        mem_kb = int(mem)
                    except ValueError:
                        mem_kb = 0
                    try:
                        pid_int = int(pid)
                    except ValueError:
                        pid_int = 0
                    procs.append({
                        "pid": pid_int,
                        "name": name,
                        "mem_kb": mem_kb,
                        "user": "",
                    })
        elif is_android() or is_linux():
            out = subprocess.run(
                'ps -eo pid,user,comm,rss',
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            ).stdout or ""
            lines = out.strip().splitlines()
            if len(lines) >= 2:
                for line in lines[1:]:
                    parts = line.split(None, 3)
                    if len(parts) < 4:
                        continue
                    pid_s, user, comm, rss_s = parts
                    try:
                        pid_int = int(pid_s)
                        mem_kb = int(rss_s)
                    except ValueError:
                        continue
                    procs.append({
                        "pid": pid_int,
                        "name": comm,
                        "mem_kb": mem_kb,
                        "user": user,
                    })
    except Exception as e:
        return [{"pid": 0, "name": f"[ERROR] {e}", "mem_kb": 0, "user": ""}]
    return procs


def human_kb(kb):
    if kb < 1024:
        return f"{kb} K"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    return f"{gb:.2f} GB"


def human_bytes(b):
    try:
        b = float(b)
    except (TypeError, ValueError):
        return "?"
    if b < 1024:
        return f"{b:.0f} B"
    kb = b / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    if gb < 1024:
        return f"{gb:.2f} GB"
    tb = gb / 1024
    return f"{tb:.2f} TB"


def _safe_run(cmd, timeout=15):
    """Utility: run a command and return stdout safely (UTF-8 + replace)."""
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return r.stdout or ""
    except Exception:
        return ""


# ============================================================
#  VRAM (REGISTRY METHOD — 64-BIT, NO 4GB CAP)
# ============================================================
def _read_vram_from_registry(gpu_name):
    try:
        base = r"HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"

        r = _safe_run(f'reg query "{base}" /s /v HardwareInformation.qwMemorySize', timeout=15)

        current_key = None
        vram_by_key = {}
        for line in r.splitlines():
            line = line.strip()
            if line.startswith("HKEY_"):
                current_key = line
            elif "HardwareInformation.qwMemorySize" in line:
                parts = line.split()
                if len(parts) >= 3:
                    hexval = parts[-1]
                    try:
                        vram_by_key[current_key] = int(hexval, 16)
                    except ValueError:
                        pass

        if not vram_by_key:
            return None

        if gpu_name:
            for key, vram in vram_by_key.items():
                r2 = _safe_run(f'reg query "{key}" /v DriverDesc', timeout=10)
                if gpu_name.lower() in r2.lower():
                    return vram

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
        if line.startswith("Name="):
            info["cpu_name"] = line.split("=", 1)[1]
        elif line.startswith("NumberOfCores="):
            info["cpu_cores"] = line.split("=", 1)[1]
        elif line.startswith("NumberOfLogicalProcessors="):
            info["cpu_threads"] = line.split("=", 1)[1]
        elif line.startswith("MaxClockSpeed="):
            info["cpu_mhz"] = line.split("=", 1)[1]

    r = _safe_run('wmic computersystem get TotalPhysicalMemory /format:list')
    for line in r.splitlines():
        if line.strip().startswith("TotalPhysicalMemory="):
            try:
                info["ram_bytes"] = int(line.strip().split("=", 1)[1])
            except ValueError:
                pass

    r = _safe_run('wmic path win32_VideoController get Name /format:list')
    gpus = []
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Name=") and line.split("=", 1)[1]:
            gpus.append({"name": line.split("=", 1)[1]})
    for g in gpus:
        g["vram"] = _read_vram_from_registry(g.get("name", ""))
    if gpus:
        info["gpus"] = gpus

    r = _safe_run('wmic baseboard get Product,Manufacturer /format:list')
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Product=") and line.split("=", 1)[1]:
            info["motherboard"] = line.split("=", 1)[1]
        elif line.startswith("Manufacturer=") and line.split("=", 1)[1]:
            info["mobo_vendor"] = line.split("=", 1)[1]

    r = _safe_run('wmic computersystem get Manufacturer,Model /format:list')
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Manufacturer=") and line.split("=", 1)[1]:
            info["sys_vendor"] = line.split("=", 1)[1]
        elif line.startswith("Model=") and line.split("=", 1)[1]:
            info["sys_model"] = line.split("=", 1)[1]

    r = _safe_run('wmic diskdrive get Model,Size /format:list')
    cur = {}
    disks = []
    for line in r.splitlines():
        line = line.strip()
        if line.startswith("Model="):
            cur["model"] = line.split("=", 1)[1]
        elif line.startswith("Size=") and line.split("=", 1)[1].strip():
            try:
                cur["size"] = int(line.split("=", 1)[1])
            except ValueError:
                cur["size"] = None
            if "model" in cur:
                if cur.get("size"):
                    disks.append(f"{cur['model']} ({human_bytes(cur['size'])})")
                else:
                    disks.append(cur["model"])
            cur = {}
    if disks:
        info["disks"] = disks

    return info


def _linux_specs():
    info = {}

    try:
        with open("/proc/cpuinfo") as f:
            content = f.read()
        for line in content.splitlines():
            if "model name" in line and "cpu_name" not in info:
                info["cpu_name"] = line.split(":", 1)[1].strip()
            elif "Hardware" in line and "cpu_name" not in info:
                info["cpu_name"] = line.split(":", 1)[1].strip()
            elif "Processor" in line and "cpu_name" not in info:
                info["cpu_name"] = line.split(":", 1)[1].strip()
    except Exception:
        pass

    try:
        info["cpu_threads"] = str(os.cpu_count() or "?")
    except Exception:
        pass

    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    info["ram_bytes"] = kb * 1024
                    break
    except Exception:
        pass

    if is_android():
        info["sys_model"] = _safe_run("getprop ro.product.model", timeout=5).strip()
        info["sys_vendor"] = _safe_run("getprop ro.product.manufacturer", timeout=5).strip()
        android_ver = _safe_run("getprop ro.build.version.release", timeout=5).strip()
        if android_ver:
            info["android_version"] = android_ver

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
        elif line.startswith("Memory:"):
            info["ram_str"] = line.split(":", 1)[1].strip()
        elif line.startswith("Model Name:"):
            info["sys_model"] = line.split(":", 1)[1].strip()
        elif line.startswith("Model Identifier:"):
            info["sys_id"] = line.split(":", 1)[1].strip()
    return info


def collect_specs():
    if is_windows():
        return _win_specs()
    elif platform.system() == "Darwin":
        return _mac_specs()
    else:
        return _linux_specs()


# ============================================================
#  SMART PROGRAM LOOKUP (PATHFINDER)
# ============================================================
def _win_search_roots():
    roots = []
    user = os.environ.get("USERPROFILE", "")
    if user:
        roots += [
            os.path.join(user, "AppData", "Local"),
            os.path.join(user, "AppData", "Roaming"),
            os.path.join(user, "AppData", "LocalLow"),
            os.path.join(user, "Desktop"),
            os.path.join(user, "Downloads"),
        ]
    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        p = os.environ.get(env)
        if p:
            roots.append(p)
    for drive in ("C:", "D:", "E:"):
        roots.append(os.path.join(drive + os.sep, "Program Files (x86)", "Steam", "steamapps", "common"))
        roots.append(os.path.join(drive + os.sep, "SteamLibrary", "steamapps", "common"))
    return [r for r in roots if os.path.isdir(r)]


def _android_search_roots():
    roots = []
    for p in ("/data/data", "/data/app", "/system/app", "/system/priv-app"):
        if os.path.isdir(p):
            roots.append(p)
    roots.append(os.path.expanduser("~"))
    return roots


_PROGRAM_CACHE = {"list": None, "roots_key": None}


def _build_program_index():
    if is_windows():
        roots = _win_search_roots()
        ext = ".exe"
    elif is_android():
        roots = _android_search_roots()
        ext = ""
    else:
        roots = ["/usr/bin", "/usr/local/bin", "/opt", os.path.expanduser("~/.local/bin")]
        ext = ""

    key = "|".join(roots) + "|" + ext
    if _PROGRAM_CACHE["list"] is not None and _PROGRAM_CACHE["roots_key"] == key:
        return _PROGRAM_CACHE["list"]

    found = []
    for root in roots:
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            depth = dirpath.count(os.sep) - base_depth
            if depth > 4:
                dirnames[:] = []
                continue
            for f in filenames:
                if ext and f.lower().endswith(ext):
                    found.append(os.path.join(dirpath, f))
                elif not ext:
                    found.append(os.path.join(dirpath, f))

    _PROGRAM_CACHE["list"] = found
    _PROGRAM_CACHE["roots_key"] = key
    return found


def _fuzzy_score(query, target):
    q = query.lower().replace(".exe", "").strip()
    t = os.path.basename(target).lower().replace(".exe", "").strip()

    if not q or not t:
        return 0
    if q == t:
        return 1000
    if t.startswith(q):
        return 800 - len(t)
    if q in t:
        return 600 - len(t)
    q_tokens = [tok for tok in q.replace("-", " ").replace("_", " ").split() if tok]
    if q_tokens and all(tok in t for tok in q_tokens):
        return 400 - len(t)
    ti = 0
    for ch in q:
        ti = t.find(ch, ti)
        if ti == -1:
            return 0
        ti += 1
    return 100


def find_program(name):
    if os.path.isabs(name) and os.path.exists(name):
        return name

    local = os.path.join(STATE["cwd"], name)
    if os.path.exists(local):
        return local

    found = shutil.which(name)
    if found:
        return found

    print(f"[search] scanning install folders for '{name}'...")
    index = _build_program_index()

    scored = []
    for path in index:
        s = _fuzzy_score(name, path)
        if s > 0:
            scored.append((s, path))

    if not scored:
        return None

    scored.sort(reverse=True)
    best_score, best_path = scored[0]

    strong = [p for s, p in scored if s >= best_score - 100][:10]
    if len(strong) > 1 and best_score < 1000:
        print(f"[search] {len(strong)} match(es):")
        for i, p in enumerate(strong, 1):
            print(f"  {i}. {p}")
        try:
            pick = input("  Choose (number, Enter for #1): ").strip()
            if pick:
                idx = int(pick) - 1
                if 0 <= idx < len(strong):
                    return strong[idx]
        except Exception:
            pass

    return best_path


# ============================================================
#  LICENSE TEXT
# ============================================================
LICENSE_TEXT = r"""
Eclipse Shell — Proprietary License
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
    print_header("Eclipse Shell — Command List")
    for name in sorted(COMMANDS.keys()):
        desc = COMMANDS[name]["desc"]
        print(f"  {name:<12} {desc}")
    print()


@register("about", "Show information about Eclipse Shell.")
def cmd_about(args):
    print_header("About Eclipse Shell")
    print(f"  Name     : Eclipse Shell")
    print(f"  Version  : {STATE['version']} ({STATE['status']})")
    print(f"  Author   : {STATE['author']}")
    print(f"  License  : Proprietary — see 'license' command")
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {platform.python_version()}")
    print()
    print("  Cross-platform shell for Windows, Linux, macOS, and Android.")
    print()
    print(f"  Contact  : YouTube {STATE['youtube']}  |  Discord {STATE['discord']}")
    print()


@register("license", "Display the Eclipse Shell license.")
def cmd_license(args):
    print(LICENSE_TEXT)


@register("cls", "Clear the screen.")
def cmd_cls(args):
    if is_windows():
        os.system("")
    sys.stdout.write("\033[2J\033[3J\033[H")
    sys.stdout.flush()


@register("clear", "Clear the screen (alias for cls).")
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


@register("version", "Show Eclipse Shell version.")
def cmd_version(args):
    print(f"Eclipse Shell [Version {STATE['version']} {STATE['status']}]")


@register("ver", "Show Eclipse Shell version (alias).")
def cmd_ver(args):
    cmd_version(args)


@register("commands", "Count total registered commands.")
def cmd_commands(args):
    print(f"  {len(COMMANDS)} commands registered")


@register("allhelp", "List all commands in compact grid.")
def cmd_allhelp(args):
    names = sorted(COMMANDS.keys())
    print(f"  {len(names)} commands:")
    for i in range(0, len(names), 5):
        row = "  ".join(f"{n:<12}" for n in names[i:i+5])
        print(f"  {row}")


@register("tips", "Show a random tip.")
def cmd_tips(args):
    tips = [
        "Use pipes: tasklist | grep chrome",
        "Redirect output: dir > files.txt",
        "Find app easily: start notepad",
        "Check specs: sysinfo",
        "Add text to file: append notes.txt hello",
        "Tree view: tree",
        "Search files: findext py",
        "Find TODOs: todo",
    ]
    print(f"  Tip: {random.choice(tips)}")


# ============================================================
#  FILESYSTEM COMMANDS
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


@register("ls", "List directory contents (Unix-style).")
def cmd_ls(args):
    target = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(target):
        print(f"[ERROR] Not a directory: {target}")
        return
    try:
        for e in sorted(os.listdir(target)):
            full = os.path.join(target, e)
            suffix = "/" if os.path.isdir(full) else ""
            print(e + suffix)
    except PermissionError:
        print(f"[ERROR] Access denied: {target}")


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


@register("cat", "Print contents of a file (alias for type).")
def cmd_cat(args):
    cmd_type(args)


@register("mkdir", "Create a directory.  Usage: mkdir <name>")
def cmd_mkdir(args):
    if not args:
        print("[ERROR] Usage: mkdir <name>")
        return
    path = resolve_path(args[0])
    try:
        os.makedirs(path, exist_ok=True)
        print(f"[ok] Created {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("rm", "Remove a file.  Usage: rm <file>")
def cmd_rm(args):
    if not args:
        print("[ERROR] Usage: rm <file>")
        return
    path = resolve_path(args[0])
    if not os.path.exists(path):
        print(f"[ERROR] Not found: {path}")
        return
    try:
        if os.path.isdir(path):
            print("[ERROR] Use 'rmdir' for directories.")
            return
        os.remove(path)
        print(f"[ok] Removed {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("rmdir", "Remove an empty directory.  Usage: rmdir <dir>")
def cmd_rmdir(args):
    if not args:
        print("[ERROR] Usage: rmdir <dir>")
        return
    path = resolve_path(args[0])
    try:
        os.rmdir(path)
        print(f"[ok] Removed {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("find", "Find files by name.  Usage: find <name>")
def cmd_find(args):
    if not args:
        print("[ERROR] Usage: find <name>")
        return
    needle = args[0].lower()
    hits = 0
    for root, dirs, files in os.walk(STATE["cwd"]):
        for f in files + dirs:
            if needle in f.lower():
                print(os.path.join(root, f))
                hits += 1
                if hits >= 200:
                    print("[...truncated]")
                    return
    if hits == 0:
        print("[no matches]")


@register("grep", "Search inside files.  Usage: grep <pattern> <file>")
def cmd_grep(args):
    if len(args) < 2:
        print("[ERROR] Usage: grep <pattern> <file>")
        return
    pattern = args[0]
    path = resolve_path(args[1])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if pattern in line:
                    print(f"{i}: {line.rstrip()}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("head", "Show first lines of a file.  Usage: head <file> [n]")
def cmd_head(args):
    if not args:
        print("[ERROR] Usage: head <file> [n]")
        return
    n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
    path = resolve_path(args[0])
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                print(line.rstrip())
    except Exception as e:
        print(f"[ERROR] {e}")


@register("tail", "Show last lines of a file.  Usage: tail <file> [n]")
def cmd_tail(args):
    if not args:
        print("[ERROR] Usage: tail <file> [n]")
        return
    n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
    path = resolve_path(args[0])
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in lines[-n:]:
            print(line.rstrip())
    except Exception as e:
        print(f"[ERROR] {e}")


@register("wc", "Count lines/words/chars.  Usage: wc <file>")
def cmd_wc(args):
    if not args:
        print("[ERROR] Usage: wc <file>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        lines = data.count("\n")
        words = len(data.split())
        chars = len(data)
        print(f"  {lines}  {words}  {chars}  {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("df", "Disk usage.  Usage: df [path]")
def cmd_df(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    if is_windows():
        out = run_shell("wmic logicaldisk get size,freespace,caption")
    else:
        out = run_shell(f"df -h '{path}'")
    print(out)


# ============================================================
#  FILE OPS
# ============================================================
@register("cp", "Copy a file.  Usage: cp <src> <dst>")
def cmd_cp(args):
    if len(args) < 2:
        print("[ERROR] Usage: cp <src> <dst>")
        return
    src = resolve_path(args[0])
    dst = resolve_path(args[1])
    if not os.path.exists(src):
        print(f"[ERROR] Source not found: {src}")
        return
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"[ok] Copied {src} -> {dst}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("mv", "Move/rename a file.  Usage: mv <src> <dst>")
def cmd_mv(args):
    if len(args) < 2:
        print("[ERROR] Usage: mv <src> <dst>")
        return
    src = resolve_path(args[0])
    dst = resolve_path(args[1])
    if not os.path.exists(src):
        print(f"[ERROR] Source not found: {src}")
        return
    try:
        shutil.move(src, dst)
        print(f"[ok] Moved {src} -> {dst}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("touch", "Create an empty file.  Usage: touch <file>")
def cmd_touch(args):
    if not args:
        print("[ERROR] Usage: touch <file>")
        return
    path = resolve_path(args[0])
    try:
        with open(path, "a", encoding="utf-8"):
            pass
        print(f"[ok] Touched {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("write", "Write text to a file.  Usage: write <file> <text...>")
def cmd_write(args):
    if len(args) < 2:
        print("[ERROR] Usage: write <file> <text...>")
        return
    path = resolve_path(args[0])
    text = " ".join(args[1:])
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[ok] Wrote to {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("append", "Append text to a file.  Usage: append <file> <text...>")
def cmd_append(args):
    if len(args) < 2:
        print("[ERROR] Usage: append <file> <text...>")
        return
    path = resolve_path(args[0])
    text = " ".join(args[1:])
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[ok] Appended to {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("rename", "Rename a file.  Usage: rename <old> <new>")
def cmd_rename(args):
    if len(args) < 2:
        print("[ERROR] Usage: rename <old> <new>")
        return
    cmd_mv(args)


@register("tree", "Show directory tree.  Usage: tree [path] [depth]")
def cmd_tree(args):
    root = resolve_path(args[0]) if args else STATE["cwd"]
    max_depth = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
    if not os.path.isdir(root):
        print(f"[ERROR] Not a directory: {root}")
        return

    def walk(path, prefix, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            print(f"{prefix}[access denied]")
            return
        for i, e in enumerate(entries):
            full = os.path.join(path, e)
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            print(f"{prefix}{connector}{e}")
            if os.path.isdir(full):
                extension = "    " if is_last else "│   "
                walk(full, prefix + extension, depth + 1)

    print(root)
    walk(root, "", 1)


@register("size", "Show size of a file/folder.  Usage: size <path>")
def cmd_size(args):
    if not args:
        print("[ERROR] Usage: size <path>")
        return
    path = resolve_path(args[0])
    if not os.path.exists(path):
        print(f"[ERROR] Not found: {path}")
        return
    if os.path.isfile(path):
        print(f"{human_bytes(os.path.getsize(path))}  {path}")
        return
    total = 0
    count = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
                count += 1
            except Exception:
                pass
    print(f"{human_bytes(total)}  {count} files  {path}")


# ============================================================
#  ARCHIVE / COMPRESSION
# ============================================================
@register("zip", "Zip a file or folder.  Usage: zip <src> [output.zip]")
def cmd_zip(args):
    if not args:
        print("[ERROR] Usage: zip <src> [output.zip]")
        return
    src = resolve_path(args[0])
    if not os.path.exists(src):
        print(f"[ERROR] Not found: {src}")
        return
    if len(args) > 1:
        out = resolve_path(args[1])
    else:
        out = os.path.join(STATE["cwd"], os.path.basename(src.rstrip("/\\")) + ".zip")
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(src):
                zf.write(src, os.path.basename(src))
            else:
                for root, dirs, files in os.walk(src):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = os.path.relpath(full, os.path.dirname(src))
                        zf.write(full, arc)
        print(f"[ok] Zipped -> {out}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("unzip", "Extract a .zip file.  Usage: unzip <file.zip> [dest]")
def cmd_unzip(args):
    if not args:
        print("[ERROR] Usage: unzip <file.zip> [dest]")
        return
    src = resolve_path(args[0])
    if not os.path.isfile(src):
        print(f"[ERROR] File not found: {src}")
        return
    dest = resolve_path(args[1]) if len(args) > 1 else os.path.splitext(src)[0]
    try:
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(dest)
        print(f"[ok] Extracted -> {dest}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("tar", "Tar a folder.  Usage: tar <src> [output.tar.gz]")
def cmd_tar(args):
    if not args:
        print("[ERROR] Usage: tar <src> [output.tar.gz]")
        return
    src = resolve_path(args[0])
    if not os.path.exists(src):
        print(f"[ERROR] Not found: {src}")
        return
    if len(args) > 1:
        out = resolve_path(args[1])
    else:
        out = os.path.join(STATE["cwd"], os.path.basename(src.rstrip("/\\")) + ".tar.gz")
    try:
        with tarfile.open(out, "w:gz") as tf:
            tf.add(src, arcname=os.path.basename(src.rstrip("/\\")))
        print(f"[ok] Tarball -> {out}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("untar", "Extract a .tar.gz file.  Usage: untar <file.tar.gz> [dest]")
def cmd_untar(args):
    if not args:
        print("[ERROR] Usage: untar <file.tar.gz> [dest]")
        return
    src = resolve_path(args[0])
    if not os.path.isfile(src):
        print(f"[ERROR] File not found: {src}")
        return
    dest = resolve_path(args[1]) if len(args) > 1 else STATE["cwd"]
    try:
        with tarfile.open(src, "r:gz") as tf:
            tf.extractall(dest)
        print(f"[ok] Extracted -> {dest}")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  CLIPBOARD
# ============================================================
@register("clip", "Copy a file's contents to clipboard.  Usage: clip <file>")
def cmd_clip(args):
    if not args:
        print("[ERROR] Usage: clip <file>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        if is_windows():
            subprocess.run("clip", input=data, text=True, shell=True)
        elif is_android():
            subprocess.run("termux-clipboard-set", input=data, text=True, shell=True)
        else:
            print("[ERROR] 'clip' works on Windows and Android only.")
            return
        print(f"[ok] Copied {len(data)} chars to clipboard")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("paste", "Show clipboard contents.")
def cmd_paste(args):
    try:
        if is_windows():
            out = _safe_run("powershell Get-Clipboard", timeout=10)
        elif is_android():
            out = _safe_run("termux-clipboard-get", timeout=10)
        else:
            print("[ERROR] 'paste' works on Windows and Android only.")
            return
        print(out if out.strip() else "[empty clipboard]")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  SYSTEM / UTILITY
# ============================================================
@register("echo", "Print a message.  Usage: echo <text>")
def cmd_echo(args):
    print(" ".join(args))


@register("whoami", "Show the current Eclipse user.")
def cmd_whoami(args):
    print(STATE["user"])


@register("sysinfo", "Show full hardware specs of this machine.")
def cmd_sysinfo(args):
    specs = collect_specs()

    print_header("System Information")

    os_line = f"{platform.system()} {platform.release()}"
    if is_android():
        ver = specs.get("android_version", "")
        os_line = f"Android {ver}" if ver else "Android"
    print(f"  OS         : {os_line}")
    print(f"  Hostname   : {platform.node() or '?'}")
    print(f"  Arch       : {platform.machine() or '?'}")
    print(f"  Python     : {platform.python_version()}")
    print()

    vendor = specs.get("sys_vendor")
    model = specs.get("sys_model")
    if vendor or model:
        print(f"  System     : {vendor or '?'} {model or ''}".rstrip())

    if specs.get("motherboard"):
        mobo = specs["motherboard"]
        if specs.get("mobo_vendor"):
            mobo = f"{specs['mobo_vendor']} {mobo}"
        print(f"  Motherboard: {mobo}")

    cpu = specs.get("cpu_name", platform.processor() or "?")
    cpu_line = cpu
    cores = specs.get("cpu_cores")
    threads = specs.get("cpu_threads")
    mhz = specs.get("cpu_mhz")
    extras = []
    if cores:
        extras.append(f"{cores} cores")
    if threads:
        extras.append(f"{threads} threads")
    if mhz:
        try:
            extras.append(f"{float(mhz)/1000:.2f} GHz")
        except ValueError:
            pass
    if extras:
        cpu_line = f"{cpu} ({', '.join(extras)})"
    print(f"  CPU        : {cpu_line}")

    if specs.get("ram_bytes"):
        print(f"  RAM        : {human_bytes(specs['ram_bytes'])}")
    elif specs.get("ram_str"):
        print(f"  RAM        : {specs['ram_str']}")

    gpus = specs.get("gpus")
    if gpus:
        for i, g in enumerate(gpus):
            label = "GPU" if i == 0 else "           "
            name = g.get("name", "?")
            vram = g.get("vram")
            if vram and vram > 0:
                print(f"  {label}        : {name} ({human_bytes(vram)} VRAM)")
            else:
                print(f"  {label}        : {name}")

    if specs.get("disks"):
        print(f"  Disks      :")
        for d in specs["disks"]:
            print(f"               - {d}")

    print()


@register("os", "Show operating system info.")
def cmd_os(args):
    print_header("Operating System")
    print(f"  System   : {platform.system()}")
    print(f"  Release  : {platform.release()}")
    print(f"  Version  : {platform.version()}")
    print(f"  Arch     : {platform.machine()}")
    print(f"  Node     : {platform.node()}")
    print(f"  Python   : {platform.python_version()}")
    print()


@register("cpu", "Show CPU info.")
def cmd_cpu(args):
    if is_windows():
        out = run_shell("wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed /format:list")
    elif is_android() or is_linux():
        out = run_shell("cat /proc/cpuinfo | head -30")
    else:
        out = run_shell("sysctl -n machdep.cpu.brand_string")
    print(out)


@register("mem", "Show memory usage.")
def cmd_mem(args):
    if is_windows():
        out = run_shell("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /format:list")
    else:
        out = run_shell("free -h || cat /proc/meminfo | head -5")
    print(out)


@register("gpu", "Show GPU info.")
def cmd_gpu(args):
    if is_windows():
        out = run_shell("wmic path win32_VideoController get Name /format:list")
    elif is_android() or is_linux():
        out = run_shell("lspci | grep -i vga || dumpsys SurfaceFlinger | grep -i gpu | head -5")
    else:
        out = run_shell("system_profiler SPDisplaysDataType")
    print(out)


@register("hostname", "Show or set hostname.  Usage: hostname [name]")
def cmd_hostname(args):
    if args:
        STATE["host"] = args[0]
        print(f"[host] -> {args[0]}")
    else:
        print(platform.node())


@register("user", "Show current user.")
def cmd_user(args):
    print(STATE["user"])


@register("env", "Show environment variables.  Usage: env [var]")
def cmd_env(args):
    if args:
        val = os.environ.get(args[0])
        print(val if val else f"[empty] {args[0]} not set")
        return
    for k, v in sorted(os.environ.items()):
        print(f"  {k}={v}")


@register("time", "Show current system time.")
def cmd_time(args):
    print(time.strftime("%Y-%m-%d %H:%M:%S"))


@register("date", "Show current date.")
def cmd_date(args):
    print(time.strftime("%Y-%m-%d"))


@register("uptime", "Show system uptime.")
def cmd_uptime(args):
    if is_windows():
        out = run_shell("net statistics workstation")
    else:
        out = run_shell("uptime")
    print(out)


# ============================================================
#  SYSTEM TWEAKS
# ============================================================
@register("temp", "Show or clear temp files.  Usage: temp [clear]")
def cmd_temp(args):
    tmpdir = tempfile.gettempdir()
    if args and args[0].lower() == "clear":
        count = 0
        for f in os.listdir(tmpdir):
            try:
                full = os.path.join(tmpdir, f)
                if os.path.isfile(full):
                    os.remove(full)
                    count += 1
                elif os.path.isdir(full):
                    shutil.rmtree(full, ignore_errors=True)
                    count += 1
            except Exception:
                pass
        print(f"[ok] Cleared {count} item(s) from temp")
        return
    print(f"  Temp: {tmpdir}")
    try:
        files = os.listdir(tmpdir)
        total = 0
        for f in files:
            try:
                total += os.path.getsize(os.path.join(tmpdir, f))
            except Exception:
                pass
        print(f"  Files: {len(files)}")
        print(f"  Size : {human_bytes(total)}")
        print(f"  [tip] Run 'temp clear' to empty it.")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("proc", "Show quick process count.")
def cmd_proc(args):
    procs = get_processes()
    print(f"  Running processes: {len(procs)}")


@register("top5", "Show top 5 processes.")
def cmd_top5(args):
    cmd_top(["5"])


@register("services", "List running services (Windows only).")
def cmd_services(args):
    if not is_windows():
        print("[ERROR] 'services' is Windows-only.")
        return
    print(run_shell("sc query type= service state= all | findstr SERVICE_NAME"))


@register("startup", "List startup programs (Windows only).")
def cmd_startup(args):
    if not is_windows():
        print("[ERROR] 'startup' is Windows-only.")
        return
    print(run_shell('wmic startup get Caption,Command'))


@register("drivers", "List installed drivers (Windows only).")
def cmd_drivers(args):
    if not is_windows():
        print("[ERROR] 'drivers' is Windows-only.")
        return
    print(run_shell("driverquery"))


# ============================================================
#  TEXT TOOLS
# ============================================================
@register("sort", "Sort lines of a file.  Usage: sort <file>")
def cmd_sort(args):
    if not args:
        print("[ERROR] Usage: sort <file>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in sorted(f):
                print(line.rstrip())
    except Exception as e:
        print(f"[ERROR] {e}")


@register("uniq", "Remove duplicate lines.  Usage: uniq <file>")
def cmd_uniq(args):
    if not args:
        print("[ERROR] Usage: uniq <file>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        seen = set()
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line not in seen:
                    seen.add(line)
                    print(line.rstrip())
    except Exception as e:
        print(f"[ERROR] {e}")


@register("rev", "Reverse each line.  Usage: rev <file>")
def cmd_rev(args):
    if not args:
        print("[ERROR] Usage: rev <file>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                print(line.rstrip()[::-1])
    except Exception as e:
        print(f"[ERROR] {e}")


@register("replace", "Replace text in a file.  Usage: replace <file> <old> <new>")
def cmd_replace(args):
    if len(args) < 3:
        print("[ERROR] Usage: replace <file> <old> <new>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    old, new = args[1], args[2]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        count = data.count(old)
        data = data.replace(old, new)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
        print(f"[ok] Replaced {count} occurrence(s)")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("lines", "Count lines in a file.  Usage: lines <file>")
def cmd_lines(args):
    if not args:
        print("[ERROR] Usage: lines <file>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            count = sum(1 for _ in f)
        print(f"  {count} lines  {path}")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  DEV / CODING TOOLS
# ============================================================
@register("py", "Run a Python file.  Usage: py <file.py> [args...]")
def cmd_py(args):
    if not args:
        print("[ERROR] Usage: py <file.py> [args...]")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    script_args = args[1:]
    cmd = f'python "{path}" ' + " ".join(script_args)
    run_shell(cmd, live=True, timeout=300)


@register("json", "Pretty-print a JSON file.  Usage: json <file>")
def cmd_json(args):
    if not args:
        print("[ERROR] Usage: json <file>")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}")


@register("hex", "Show file hex dump.  Usage: hex <file> [n]")
def cmd_hex(args):
    if not args:
        print("[ERROR] Usage: hex <file> [n]")
        return
    path = resolve_path(args[0])
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 256
    try:
        with open(path, "rb") as f:
            data = f.read(limit)
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hexpart = " ".join(f"{b:02x}" for b in chunk)
            asciipart = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"  {i:08x}  {hexpart:<48}  {asciipart}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("count", "Count files by extension.  Usage: count [path]")
def cmd_count(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    if not os.path.isdir(path):
        print(f"[ERROR] Not a directory: {path}")
        return
    ext_count = {}
    for root, dirs, files in os.walk(path):
        for f in files:
            ext = os.path.splitext(f)[1].lower() or "(none)"
            ext_count[ext] = ext_count.get(ext, 0) + 1
    sorted_ext = sorted(ext_count.items(), key=lambda x: x[1], reverse=True)
    print_header(f"File Counts — {path}")
    for ext, count in sorted_ext[:30]:
        print(f"  {count:>6}  {ext}")
    print()


@register("todo", "Find TODO/FIXME comments in code.  Usage: todo [path]")
def cmd_todo(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", "venv")]
        for f in files:
            if not f.endswith((".py", ".js", ".ts", ".c", ".cpp", ".h", ".java", ".md", ".txt")):
                continue
            full = os.path.join(root, f)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        up = line.upper()
                        if "TODO" in up or "FIXME" in up or "XXX" in up:
                            print(f"  {full}:{i}  {line.strip()[:80]}")
                            count += 1
            except Exception:
                pass
    print(f"\n  {count} match(es)")


# ============================================================
#  BATCH OPERATIONS
# ============================================================
@register("findext", "Find all files with extension.  Usage: findext <ext>")
def cmd_findext(args):
    if not args:
        print("[ERROR] Usage: findext <ext>")
        return
    ext = args[0]
    if not ext.startswith("."):
        ext = "." + ext
    hits = 0
    for root, dirs, files in os.walk(STATE["cwd"]):
        for f in files:
            if f.lower().endswith(ext.lower()):
                print(os.path.join(root, f))
                hits += 1
                if hits >= 300:
                    print("[...truncated]")
                    return
    if hits == 0:
        print(f"[no {ext} files found]")


@register("renameall", "Rename all files matching ext.  Usage: renameall <ext> <newname>")
def cmd_renameall(args):
    if len(args) < 2:
        print("[ERROR] Usage: renameall <ext> <newname>")
        return
    ext = args[0]
    if not ext.startswith("."):
        ext = "." + ext
    base = args[1]
    count = 0
    for f in sorted(os.listdir(STATE["cwd"])):
        if f.lower().endswith(ext.lower()):
            new = f"{base}_{count}{ext}"
            try:
                os.rename(os.path.join(STATE["cwd"], f), os.path.join(STATE["cwd"], new))
                print(f"  {f} -> {new}")
                count += 1
            except Exception as e:
                print(f"  [ERROR] {f}: {e}")
    print(f"[ok] Renamed {count} file(s)")


@register("empty", "Find empty files.  Usage: empty [path]")
def cmd_empty(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    count = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            full = os.path.join(root, f)
            try:
                if os.path.getsize(full) == 0:
                    print(f"  {full}")
                    count += 1
                    if count >= 100:
                        print("[...truncated]")
                        return
            except Exception:
                pass
    print(f"\n  {count} empty file(s)")


@register("dup", "Find duplicate files by name.  Usage: dup [path]")
def cmd_dup(args):
    path = resolve_path(args[0]) if args else STATE["cwd"]
    by_name = {}
    for root, dirs, files in os.walk(path):
        for f in files:
            by_name.setdefault(f, []).append(os.path.join(root, f))
    dups = {k: v for k, v in by_name.items() if len(v) > 1}
    if not dups:
        print("[no duplicates]")
        return
    for name, paths in dups.items():
        print(f"  {name}:")
        for p in paths:
            print(f"    {p}")
    print(f"\n  {len(dups)} duplicate name(s)")


@register("bigfiles", "Find biggest files.  Usage: bigfiles [n]")
def cmd_bigfiles(args):
    n = int(args[0]) if args and args[0].isdigit() else 15
    files = []
    for root, dirs, fs in os.walk(STATE["cwd"]):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
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
#  TIME / DATE EXTRAS
# ============================================================
@register("timestamp", "Show Unix timestamp.")
def cmd_timestamp(args):
    print(f"  {int(time.time())}")


@register("calendar", "Show this month's calendar.")
def cmd_calendar(args):
    import calendar as _cal
    now = datetime.datetime.now()
    _cal.prmonth(now.year, now.month)


@register("daysuntil", "Days until a date.  Usage: daysuntil YYYY-MM-DD")
def cmd_daysuntil(args):
    if not args:
        print("[ERROR] Usage: daysuntil YYYY-MM-DD")
        return
    try:
        target = datetime.datetime.strptime(args[0], "%Y-%m-%d")
        delta = (target - datetime.datetime.now()).days
        print(f"  {delta} day(s)")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  UTILITY / FUN
# ============================================================
@register("calc", "Calculate an expression.  Usage: calc <expr>")
def cmd_calc(args):
    if not args:
        print("[ERROR] Usage: calc <expr>")
        return
    expr = " ".join(args)
    try:
        result = eval(expr, {"__builtins__": {}}, {})
        print(f"  {result}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("random", "Random number.  Usage: random [min] [max]")
def cmd_random(args):
    lo = int(args[0]) if args and args[0].lstrip("-").isdigit() else 1
    hi = int(args[1]) if len(args) > 1 and args[1].lstrip("-").isdigit() else 100
    print(f"  {random.randint(lo, hi)}")


@register("uuid", "Generate a UUID.")
def cmd_uuid(args):
    import uuid as _uuid
    print(f"  {_uuid.uuid4()}")


@register("hash", "Hash a string.  Usage: hash <algo> <text>")
def cmd_hash(args):
    if len(args) < 2:
        print("[ERROR] Usage: hash <md5|sha1|sha256|sha512> <text>")
        return
    algo = args[0].lower()
    text = " ".join(args[1:])
    if algo not in ("md5", "sha1", "sha256", "sha512"):
        print("[ERROR] Try: md5, sha1, sha256, sha512")
        return
    h = hashlib.new(algo, text.encode()).hexdigest()
    print(f"  {h}")


@register("base64", "Base64 encode/decode.  Usage: base64 [-d] <text>")
def cmd_base64(args):
    import base64 as _b64
    if not args:
        print("[ERROR] Usage: base64 [-d] <text>")
        return
    decode = args[0] == "-d"
    text = " ".join(args[1:] if decode else args)
    try:
        if decode:
            print(_b64.b64decode(text.encode()).decode())
        else:
            print(_b64.b64encode(text.encode()).decode())
    except Exception as e:
        print(f"[ERROR] {e}")


@register("now", "Show current date and time.")
def cmd_now(args):
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@register("stopwatch", "Simple stopwatch.  Press Enter to stop.")
def cmd_stopwatch(args):
    print("[stopwatch] Press Enter to stop...")
    start = time.time()
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
    elapsed = time.time() - start
    print(f"  Elapsed: {elapsed:.2f} seconds")


@register("cowsay", "Cow says something.  Usage: cowsay <text>")
def cmd_cowsay(args):
    text = " ".join(args) if args else "Hello from Eclipse Shell!"
    border = "-" * (len(text) + 2)
    print(f"  {border}")
    print(f"  {text}")
    print(f"  {border}")
    print("        \\   ^__^")
    print("         \\  (oo)\\_______")
    print("            (__)\\       )\\/\\")
    print("                ||----w |")
    print("                ||     ||")


@register("matrix", "Fake Matrix rain.")
def cmd_matrix(args):
    try:
        for _ in range(20):
            row = "".join(random.choice("01 ") for _ in range(60))
            print(f"  {row}")
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass


@register("dice", "Roll a die.  Usage: dice [sides]")
def cmd_dice(args):
    sides = int(args[0]) if args and args[0].isdigit() else 6
    print(f"  [dice] {random.randint(1, sides)}")


@register("coin", "Flip a coin.")
def cmd_coin(args):
    print(f"  {'HEADS' if random.randint(0, 1) == 0 else 'TAILS'}")


@register("password", "Generate a password.  Usage: password [length]")
def cmd_password(args):
    length = int(args[0]) if args and args[0].isdigit() else 16
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pw = "".join(random.choice(chars) for _ in range(length))
    print(f"  {pw}")


@register("meme", "Random message.")
def cmd_meme(args):
    msgs = [
        "you got this",
        "ship it",
        "one more bug and then sleep",
        "it works on my machine",
        "delete node_modules and try again",
        "have you tried turning it off and on again",
        "80% done, 80% to go",
        "git commit -m 'fixed stuff'",
        "// TODO: fix this later (2026)",
        "code is poetry. broken poetry.",
    ]
    print(f"  {random.choice(msgs)}")


# ============================================================
#  PROCESS / TASKLIST COMMANDS
# ============================================================
@register("tasklist", "Show all running processes on this machine.")
def cmd_tasklist(args):
    procs = get_processes()
    if args:
        needle = args[0].lower()
        procs = [p for p in procs if needle in p["name"].lower()]
    if not procs:
        print("[no processes found]")
        return
    procs.sort(key=lambda p: p["mem_kb"], reverse=True)
    print_header(f"Eclipse Task Manager — {len(procs)} process(es)")
    print(f"  {'PID':>7}  {'MEM':>10}  NAME")
    print(f"  {'-'*7}  {'-'*10}  {'-'*30}")
    for p in procs:
        print(f"  {p['pid']:>7}  {human_kb(p['mem_kb']):>10}  {p['name']}")
    print()


@register("ps", "List running processes (alias for tasklist).")
def cmd_ps(args):
    cmd_tasklist(args)


@register("top", "Show top processes by memory.  Usage: top [n]")
def cmd_top(args):
    n = int(args[0]) if args and args[0].isdigit() else 15
    procs = get_processes()
    procs.sort(key=lambda p: p["mem_kb"], reverse=True)
    print_header(f"Top {n} processes by memory")
    print(f"  {'PID':>7}  {'MEM':>10}  NAME")
    print(f"  {'-'*7}  {'-'*10}  {'-'*30}")
    for p in procs[:n]:
        print(f"  {p['pid']:>7}  {human_kb(p['mem_kb']):>10}  {p['name']}")
    print()


@register("taskinfo", "Details for one process.  Usage: taskinfo <pid|name>")
def cmd_taskinfo(args):
    if not args:
        print("[ERROR] Usage: taskinfo <pid|name>")
        return
    target = args[0]
    procs = get_processes()
    if target.isdigit():
        tid = int(target)
        matches = [p for p in procs if p["pid"] == tid]
    else:
        needle = target.lower()
        matches = [p for p in procs if needle in p["name"].lower()]
    if not matches:
        print(f"[ERROR] No process matched '{target}'.")
        return
    for p in matches:
        print_header(f"Process: {p['name']}")
        print(f"  PID      : {p['pid']}")
        print(f"  Memory   : {human_kb(p['mem_kb'])}")
        print(f"  User     : {p['user'] or '(unknown)'}")
        print()


@register("kill", "Kill a process.  Usage: kill <pid>")
def cmd_kill(args):
    if not args:
        print("[ERROR] Usage: kill <pid>")
        return
    pid = args[0]
    if is_windows():
        cmd = f"taskkill /PID {pid} /F"
    else:
        cmd = f"kill -9 {pid}"
    print(run_shell(cmd))


@register("battery", "Show battery info.")
def cmd_battery(args):
    if is_android():
        print(run_shell("termux-battery-status"))
    elif is_windows():
        print(run_shell("WMIC Path Win32_Battery Get EstimatedChargeRemaining"))
    else:
        print(run_shell("upower -i $(upower -e | grep BAT)"))


@register("storage", "Show storage info.")
def cmd_storage(args):
    if is_android():
        print(run_shell("termux-storage-get 2>/dev/null || df -h"))
    elif is_windows():
        print(run_shell("wmic logicaldisk get size,freespace,caption"))
    else:
        print(run_shell("df -h"))


@register("apps", "List installed Android apps (Android only).")
def cmd_apps(args):
    if not is_android():
        print("[ERROR] 'apps' only works on Android (Termux).")
        return
    print(run_shell("pm list packages | head -50"))


# ============================================================
#  START COMMAND
# ============================================================
@register("start", "Launch a program.  Usage: start <program> [args...]")
def cmd_start(args):
    if not args:
        print("[ERROR] Usage: start <program> [args...]")
        return

    program = args[0]
    program_args = args[1:]
    path = find_program(program)

    if not path:
        print(f"[ERROR] Program not found: {program}")
        return

    try:
        if is_windows():
            subprocess.Popen(f'start "" "{path}" ' + " ".join(program_args), shell=True)
        else:
            subprocess.Popen(
                [path] + program_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        print(f"[start] Launched: {path}")
    except Exception as e:
        print(f"[ERROR] Could not launch: {e}")


# ============================================================
#  NETWORK COMMANDS
# ============================================================
@register("wlan", "List saved WiFi profiles.  Usage: wlan [profile <name>]")
def cmd_wlan(args):
    if is_windows():
        if args and args[0].lower() == "profile" and len(args) >= 2:
            name = " ".join(args[1:])
            cmd = f'netsh wlan show profile name="{name}" key=clear'
        else:
            cmd = "netsh wlan show profile"
        print(run_shell(cmd, timeout=30))
    elif is_android():
        print(run_shell("dumpsys wifi | grep -i ssid"))
    else:
        print("[ERROR] 'wlan' supports Windows and Android only.")


@register("ping", "Ping an IP or hostname.  Usage: ping <host> [count]")
def cmd_ping(args):
    if not args:
        print("[ERROR] Usage: ping <host> [count]")
        return
    host = args[0]
    count = args[1] if len(args) > 1 else "4"
    flag = "-n" if is_windows() else "-c"
    run_shell(f"ping {flag} {count} {host}", live=True)


@register("ip", "Show IP configuration.")
def cmd_ip(args):
    if is_windows():
        print(run_shell("ipconfig"))
    else:
        print(run_shell("ip addr || ifconfig"))


@register("ifconfig", "Show network interfaces.")
def cmd_ifconfig(args):
    cmd_ip(args)


@register("netstat", "Show network connections.")
def cmd_netstat(args):
    print(run_shell("netstat -an"))


@register("route", "Show routing table.")
def cmd_route(args):
    if is_windows():
        print(run_shell("route print"))
    else:
        print(run_shell("ip route || route -n"))


@register("arp", "Show ARP table.")
def cmd_arp(args):
    print(run_shell("arp -a"))


@register("nslookup", "DNS lookup.  Usage: nslookup <host>")
def cmd_nslookup(args):
    if not args:
        print("[ERROR] Usage: nslookup <host>")
        return
    print(run_shell(f"nslookup {args[0]}"))


@register("tracert", "Trace route.  Usage: tracert <host>")
def cmd_tracert(args):
    if not args:
        print("[ERROR] Usage: tracert <host>")
        return
    host = args[0]
    print(f"[tracert] tracing {host} (this can take a while)...")
    sys.stdout.flush()

    if is_windows():
        cmd = f"tracert -d -w 1000 -h 15 {host}"
    else:
        cmd = f"traceroute -n -w 1 -m 15 {host}"

    try:
        subprocess.run(cmd, shell=True, timeout=90)
    except subprocess.TimeoutExpired:
        print("\n[tracert] timed out after 90s.")
    except KeyboardInterrupt:
        print("\n[tracert] cancelled.")


@register("localip", "Show your local IP.")
def cmd_localip(args):
    import socket as _sock
    try:
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        print(f"  {ip}")
    except Exception as e:
        print(f"[ERROR] {e}")


@register("publicip", "Show your public IP.")
def cmd_publicip(args):
    out = run_shell("curl -s https://api.ipify.org", timeout=15)
    print(out)


@register("port", "Check if a port is open.  Usage: port <host> <port>")
def cmd_port(args):
    if len(args) < 2:
        print("[ERROR] Usage: port <host> <port>")
        return
    import socket as _sock
    host = args[0]
    try:
        port = int(args[1])
    except ValueError:
        print("[ERROR] Port must be a number.")
        return
    s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    s.settimeout(3)
    try:
        result = s.connect_ex((host, port))
        print(f"[{'open' if result == 0 else 'closed'}] {host}:{port}")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        s.close()


@register("curl", "Fetch a URL.  Usage: curl <url>")
def cmd_curl(args):
    if not args:
        print("[ERROR] Usage: curl <url>")
        return
    print(run_shell(f"curl -s {args[0]}", timeout=30))


@register("wget", "Download via wget.  Usage: wget <url>")
def cmd_wget(args):
    if not args:
        print("[ERROR] Usage: wget <url>")
        return
    if is_windows():
        print("[ERROR] 'wget' isn't available on Windows by default.")
        return
    print(run_shell(f"wget -qO- {args[0]}", timeout=30))


# ============================================================
#  USER COMMANDS
# ============================================================
@register("cu", "Change Eclipse username.  Usage: cu <new_username>")
def cmd_cu(args):
    if not args:
        print("[ERROR] Usage: cu <new_username>")
        return
    new_name = args[0]
    old_name = STATE["user"]
    STATE["user"] = new_name
    print(f"[user] '{old_name}' -> '{new_name}'")


# ============================================================
#  POWER COMMANDS
# ============================================================
@register("shutdown", "Shutdown the PC.  Usage: shutdown [s|r|a] [seconds]")
def cmd_shutdown(args):
    if is_windows():
        if not args:
            subprocess.run("shutdown /s /t 0", shell=True)
            return
        mode = args[0].lower()
        seconds = args[1] if len(args) > 1 else "0"
        if mode in ("s", "shutdown"):
            cmd = f"shutdown /s /t {seconds}"
        elif mode in ("r", "restart", "reboot"):
            cmd = f"shutdown /r /t {seconds}"
        elif mode in ("a", "abort"):
            cmd = "shutdown /a"
        else:
            print("[ERROR] Usage: shutdown [s|r|a] [seconds]")
            return
        subprocess.run(cmd, shell=True)
    elif is_android():
        print("[INFO] Android shutdown requires root. Trying...")
        print(run_shell("su -c 'reboot -p' || echo '[ERROR] root required'"))
    else:
        print("[ERROR] 'shutdown' supports Windows and Android only.")


@register("reboot", "Restart the device.")
def cmd_reboot(args):
    if is_windows():
        subprocess.run("shutdown /r /t 0", shell=True)
    elif is_android():
        print(run_shell("su -c 'reboot' || echo '[ERROR] root required'"))
    else:
        print("[ERROR] 'reboot' supports Windows and Android only.")


# ============================================================
#  CALL
# ============================================================
@register("call", "Call another Eclipse Shell command.  Usage: call <command> [args...]")
def cmd_call(args):
    if not args:
        print("[ERROR] Usage: call <command> [args...]")
        return
    name = args[0].lower().rstrip("()")
    sub_args = args[1:]
    target = COMMANDS.get(name)
    if not target:
        print(f"[ERROR] '{name}' is not a registered Eclipse Shell command.")
        return
    if name == "call":
        print("[ERROR] 'call' cannot call itself.")
        return
    try:
        target["fn"](sub_args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
#  REDIRECTION (> and >>)
# ============================================================
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
        print("[ERROR] Missing command or output file.")
        return True

    target_path = resolve_path(right)

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        dispatch(left)
    except SystemExit:
        raise
    except Exception as e:
        sys.stdout = old_stdout
        print(f"[ERROR] {e}")
        return True
    finally:
        sys.stdout = old_stdout

    output = buf.getvalue()
    mode = "a" if append else "w"
    try:
        with open(target_path, mode, encoding="utf-8") as f:
            f.write(output)
        action = "Appended" if append else "Wrote"
        print(f"[redirect] {action} output to {target_path}")
    except Exception as e:
        print(f"[ERROR] Could not write: {e}")

    return True


# ============================================================
#  PIPE SUPPORT
# ============================================================
def run_pipeline(line):
    segments = [s.strip() for s in line.split("|") if s.strip()]

    stdin_text = None
    for i, seg in enumerate(segments):
        parts = seg.split()
        if not parts:
            continue
        name = parts[0].lower().rstrip("()")
        args = parts[1:]

        target = COMMANDS.get(name)
        if not target:
            print(f"[ERROR] Unknown command: {name}")
            return

        is_last = (i == len(segments) - 1)

        if stdin_text is not None and name == "grep" and len(args) == 1:
            pattern = args[0]
            filtered = "\n".join(
                l for l in stdin_text.splitlines() if pattern in l
            )
            stdin_text = filtered
            if is_last:
                print(filtered)
            continue

        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            target["fn"](args)
        except SystemExit:
            raise
        except Exception as e:
            sys.stdout = old_stdout
            print(f"[ERROR] {e}")
            return
        finally:
            sys.stdout = old_stdout

        output = buf.getvalue()

        if is_last:
            print(output, end="" if output.endswith("\n") else "\n")
        else:
            stdin_text = output


# ============================================================
#  MAIN LOOP
# ============================================================
def dispatch(line):
    parts = line.strip().split()
    if not parts:
        return
    STATE["history"].append(line.strip())
    name = parts[0].lower().rstrip("()")
    args = parts[1:]
    cmd = COMMANDS.get(name)
    if not cmd:
        print(f"[ERROR] Unknown command: {name}   (type 'help' for a list)")
        return
    try:
        cmd["fn"](args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ERROR] {e}")


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
    print(f"Eclipse Shell [Version {STATE['version']} ({STATE['status']})]")
    print(f"  Copyright (c) 2026 {STATE['author']}")
    print("  Type 'help' to see commands, 'license' for terms.")
    print("  Pipes: ls | grep py    Redirect: dir > files.txt")
    print()


def main():
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
