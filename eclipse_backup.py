
#!/usr/bin/env python3
"""
Eclipse Terminal
Command registry + auto help() for the Eclipse OS.
Cross-platform commands: Windows + Android (Termux).
"""

import os
import sys
import platform
import time
import shutil
import subprocess
import csv
import io

# ============================================================
#  STATE
# ============================================================
STATE = {
    "cwd": os.getcwd(),
    "user": "eclipse",
    "host": "eclipse",
    "history": [],
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
    try:
        if live:
            subprocess.run(cmd, shell=True)
            return ""
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = result.stdout
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
    """
    Returns a list of dicts: [{'pid': int, 'name': str, 'mem_kb': int, 'user': str}]
    Real data, pulled from the actual OS.
    """
    procs = []
    try:
        if is_windows():
            # tasklist /FO CSV gives clean parseable output
            out = subprocess.run(
                'tasklist /FO CSV /NH',
                shell=True, capture_output=True, text=True, timeout=20
            ).stdout
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
            # ps -eo works on Termux and most Linux
            out = subprocess.run(
                'ps -eo pid,user,comm,rss',
                shell=True, capture_output=True, text=True, timeout=20
            ).stdout
            lines = out.strip().splitlines()
            if len(lines) >= 2:
                # Skip the header
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
    """Format KB into a friendly string."""
    if kb < 1024:
        return f"{kb} K"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    return f"{gb:.2f} GB"


# ============================================================
#  CORE COMMANDS
# ============================================================
@register("help", "List all available commands.")
def cmd_help(args):
    print_header("Eclipse Terminal — Command List")
    for name in sorted(COMMANDS.keys()):
        desc = COMMANDS[name]["desc"]
        print(f"  {name:<12} {desc}")
    print()


@register("cls", "Clear the screen.")
def cmd_cls(args):
    os.system("cls" if os.name == "nt" else "clear")


@register("clear", "Clear the screen (alias for cls).")
def cmd_clear(args):
    cmd_cls(args)


@register("exit", "Exit Eclipse Terminal.")
def cmd_exit(args):
    print("Shutting down Eclipse Terminal...")
    sys.exit(0)


@register("quit", "Exit Eclipse Terminal.")
def cmd_quit(args):
    cmd_exit(args)


@register("history", "Show command history.")
def cmd_history(args):
    if not STATE["history"]:
        print("[empty]")
        return
    for i, h in enumerate(STATE["history"], 1):
        print(f"  {i:>4}  {h}")


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
    print(f"  Android  : {is_android()}")
    print()


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
#  PROCESS / TASKLIST COMMANDS (REAL DATA)
# ============================================================
@register("tasklist", "Show all running processes on this machine.")
def cmd_tasklist(args):
    procs = get_processes()

    # Optional filter: tasklist <name>
    if args:
        needle = args[0].lower()
        procs = [p for p in procs if needle in p["name"].lower()]

    if not procs:
        print("[no processes found]")
        return

    # Sort by memory descending so heavy stuff is at top
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
    matches = []
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
    cmd = "tracert" if is_windows() else "traceroute"
    run_shell(f"{cmd} {args[0]}", live=True)


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
@register("call", "Call another Eclipse command.  Usage: call <command> [args...]")
def cmd_call(args):
    if not args:
        print("[ERROR] Usage: call <command> [args...]")
        return
    name = args[0].lower().rstrip("()")
    sub_args = args[1:]
    target = COMMANDS.get(name)
    if not target:
        print(f"[ERROR] '{name}' is not a registered Eclipse command.")
        return
    if name == "call":
        print("[ERROR] 'call' cannot call itself.")
        return
    try:
        target["fn"](sub_args)
    except Exception as e:
        print(f"[ERROR] {e}")


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
