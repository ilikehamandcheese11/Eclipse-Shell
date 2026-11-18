# Eclipse Shell

A cross-platform command shell built in Python. Works on Windows, Linux, macOS, and Android. Pure standard library, no dependencies.

## Quick Start & Download

You do not need to install Python to run Eclipse Shell. We have compiled standalone executables for both Windows and Linux!

Check the Releases tab on the right side of this page to download the latest version.

### For Windows Users
1. Download the Windows "eclipse_shell.exe" file from Eclipse Launcher (Windows-only).
2. Find and navigate to the folder where you've saved "eclipse_shell.exe". Double-click "eclipse_shell.exe" to launch.
*(Note: If Windows Defender flags the file, click "More info" and "Run anyway." This is a common false positive for compiled Python scripts).*

### For Linux Users
*(Note: These instructions are also included in the `devnote.txt` inside the Linux folder!)*
1. Download the Linux binary from Releases.
2. Open your terminal and navigate to the file via `cd`
3. **Important:** Linux is highly secure and by default refuses to run files downloaded from the internet because it doesn't know where they came from. You **MIGHT** have to give the file execution permissions by running:
   `chmod +x eclipse_shell`
4. Run the shell:
   `./eclipse_shell`

*(Why `chmod +x`? Every file in Linux has three options: Read, Write, and Execute. By default, downloaded files don't have the "Execute" permission. Running `chmod +x` tells linux to trust the file and run it.)*
---

## Please Read

The developer of this program is not responsible for any damage to your hardware caused by running certain commands in the shell. I did not and do not intend to make Eclipse Shell a malicious tool, but if you use it carelessly enough, you might run into problems. If you do not know how to use shells properly, do not use this software. 

Best wishes, 
*- ilikehamandcheese11*

---

## Features

- **188+ commands** — filesystem, system info, process management, network tools, text utilities, developer tools, and more.
- **Real hardware detection** — CPU, RAM, GPU/VRAM (read from the Windows registry for accurate 64-bit values), disks.
- **Process manager** — `tasklist`, `top`, `taskinfo`, `kill`, `top5`, and more.
- **Network tools** — `ping`, `tracert`, `port`, `nslookup`, `arp`, `netstat`, `wlan`, `httpstatus`, `whois`, and more.
- **Developer tools** — `nano` (built-in editor), `venv`, `pipfreeze`, `sha256sum`, `strings`, `jqpath`, `jsoncheck`, and more.
- **Shell features** — pipes (`|`), redirection (`>`, `>>`), aliases (`alias ll=dir`), and tab completion.
- **Categorized help** — type `help` to see commands grouped by category, or `man <command>` for full details.
- **Cross-platform** — Windows, Linux, macOS, and Android (via Termux).
- **Zero dependencies** — pure Python standard library (psutil is optional for a speed boost).

---

## Building from Source (Requirements)

If you want to run it using Python directly, or build your own binary, you will need:

- **Python 3.8 or newer**
- A real terminal (Windows Terminal, PowerShell, cmd, bash, Termux)
- **Not IDLE** — IDLE doesn't handle ANSI clear codes or live subprocess output correctly.

**On Windows:**
1st step: open Windows Terminal, PowerShell or cmd.
2nd step: execute the following commands:
```cmd
py C:\Your\Path\To\Eclipse\Shell\eclipse_backup.py OR the same command but with python instead of py.
```
after that, it should safely open on your Terminal and you can run it.
Done!

**On Linux, macOS or Android:**
1st step: open bash (Terminal).
2nd step: double click on it OR run:
```bash
cd ~/Desktop (or whereever else you saved eclipse_shell)
python3 eclipse_shell
```
this should allow Linux to run it safely on your terminal.
Done!

