# Eclipse Shell

A cross-platform command shell built in Python. Works on Windows, Linux, macOS, and Android. Pure standard library, no dependencies.

## Please Read

The developer of this program is not responsible for any damage to your hardware caused by running certain commands in the shell. I did not and do not intend to make Eclipse Shell a malicious tool, but if you use it carelessly enough, you might run into problems. If you do not know how to use shells properly, do not use this software. Best wishes - ilikehamandcheese11

## Features

- **180 commands** — filesystem, system info, process management, network tools, text utilities, developer tools, and more.
- **Real hardware detection** — CPU, RAM, GPU/VRAM (read from the Windows registry for accurate 64-bit values), disks.
- **Process manager** — `tasklist`, `top`, `taskinfo`, `kill`, `top5`, and more.
- **Network tools** — `ping`, `tracert`, `port`, `nslookup`, `arp`, `netstat`, `wlan`, `httpstatus`, `whois`, and more.
- **Developer tools** — `nano` (built-in editor), `venv`, `pipfreeze`, `sha256sum`, `strings`, `jqpath`, `jsoncheck`, and more.
- **Shell features** — pipes (`|`), redirection (`>`, `>>`), aliases (`alias ll=dir`), and tab completion.
- **Categorized help** — type `help` to see commands grouped by category, or `man <command>` for full details.
- **Cross-platform** — Windows, Linux, macOS, and Android (via Termux).
- **Zero dependencies** — pure Python standard library (psutil is optional for a speed boost).

## Requirements

- Python 3.8 or newer
- A real terminal (Windows Terminal, PowerShell, cmd, bash, Termux)
- **Not IDLE** — IDLE doesn't handle ANSI clear codes or live subprocess output correctly

## How To Run

Navigate to the folder where you saved `eclipse_shell.py`.

**On Windows:**
~~~cmd
python C:\Your\Path\To\Eclipse\Shell\eclipse_shell.py
~~~

**On Linux, macOS or Android (Termux):**
~~~bash
cd /your/path/to/eclipse_shell.py
python3 eclipse_shell.py
OR:
python3 /your/path/to/eclipse_shell.py
~~~
