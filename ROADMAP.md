# Eclipse Shell — Roadmap

Current version: **v0.6.2** (indev)
Last updated: October 28, 2026

---

## Vision

Eclipse Shell is a cross-platform command shell built in Python with
180 built-in commands. It runs on Windows, Linux, macOS, and Android
(Termux) without any dependencies — just Python 3 and the file.

The goal is a shell that is:
- **Lightweight** — single file, no install, no bloat
- **Cross-platform** — same commands on every OS
- **Honest** — real system data, no fake outputs
- **Approachable** — fun personality, not just cold utility

---

## What's Done

### v0.1.0 — Foundation
- Command registry system with `@register` decorator
- Basic filesystem commands (`cd`, `dir`, `ls`, `cat`, `rm`, `mkdir`)
- Basic system commands (`sysinfo`, `whoami`, `echo`)
- Cross-platform detection (Windows / Linux / macOS / Android)

### v0.2.0 — Shell Features
- **Pipes** — `tasklist | grep chrome`
- **Redirection** — `dir > files.txt`, `echo hello >> log.txt`
- **Scrollback clearing** — `cls` wipes history
- Fixed encoding issues on Windows (cp1251 crashes)

### v0.3.0 — Command Expansion
- 30+ new commands (filesystem, text, network, utility)
- Better hardware detection (`sysinfo` with registry VRAM)
- Real process listing with PID + memory
- Smart app launcher (`start <name>`)

### v0.3.1 — Bug Fixes
- Fixed `UnicodeDecodeError` on Windows commands
- Fixed `quit` not exiting
- Fixed `wc` crash on bad paths
- Fixed `tracert` freezing
- Better `sysinfo` output

### v0.4.0 — Major Command Expansion
- ~150 commands registered
- Startup ASCII banner restored
- `ascii-banner`, `progressbar`, `spinner`
- Math and text encoding tools (`morse`, `caesar`, `calc`)
- `fortune`, `quote`, `cowsay`, `meme`, `matrix` — personality
- `pkglist`, `info`, `os`, `cpu`, `mem`, `gpu` — quick system views

### v0.5.0 — Major Update
- **170 commands** registered
- **Up-arrow history** — recall previous commands with readline
- **Tab completion** — autocomplete command names + aliases
- **`man <command>`** — full description for any command
- **Aliases** — `alias ll=dir`, resolved in `dispatch()`
- **20 new commands added:** `man`, `alias`, `unalias`, `which`, `watch`, `bench`, `sed`, `wc-lines`, `du`, `regex`, `epoch`, `uuid7`, `url`, `jwt`, `fileinfo`, `netcheck`, `banner`, `beep`, etc.

### v0.6.2 — The Dev & Polish Update (current)
- **Massive core rewrite.** Fixed the pipe engine so stdin actually passes between *all* commands, not just `grep`. 
- **Bug fixes:** Windows encoding now uses `GetConsoleOutputCP()`, `py` uses `sys.executable`, `find`/`findext` skip `.git`/`node_modules`, `start` handles quotes properly.
- **psutil support:** Optional speedup for `tasklist`, `top`, and `proc` (falls back to native OS commands if not installed).
- **Categories are now live.** Every command is tagged (Shell, Dev, Network, etc.), so `help` and `pkglist` group them automatically.
- **22 new heavy-duty dev commands added:** `nano` (in-shell editor), `sha256sum`/`md5sum`/`sha1sum`, `xxd`, `strings`, `jqpath`, `jsoncheck`, `venv`, `pipfreeze`, `getenv`, `watchfile`, `grepdir`, `wcl`, `chmod`, `ln`, `realpath`, `basename`, `dirname`, `ext`, `mktemp`, `pgrep`, `killall`, `httpstatus`, `headers`, `dns`, `whois`, `pingport`.

---

## In Progress / Next

### v0.6.3 — Polish
- [ ] Test all 180 commands end-to-end on Windows, Linux, macOS, Android
- [ ] Fix any edge-case crashes found during testing
- [ ] Add `STDIN_CONSUMERS` support for the new commands (e.g., piping into `grepdir`)

### v0.7.0 — Power User Features
- [ ] **Environment variables** — `set NAME=value`, `$NAME` expansion
- [ ] **Wildcards** — `*.txt`, `*.py` globbing in commands
- [ ] **Command chaining** — `cmd1 && cmd2`, `cmd1 ; cmd2`
- [ ] **Background jobs** — `cmd &` to run without blocking
- [ ] **Job control** — `jobs`, `fg`, `bg` to manage them
- [ ] **History file** — persist command history between sessions (`.eclipse_history`)
- [ ] **`.eclipserc`** — user config file for defaults

### v0.8.0 — Scripting
- [ ] **Script files** — run `.ecl` files with sequences of commands
- [ ] **Script arguments** — `script.ecl arg1 arg2`
- [ ] **Variables in scripts**
- [ ] **Basic control flow** — `if`, `loop`, `for`

### v0.9.0 — Extensibility
- [ ] **Plugin system** — drop a `.py` file in `~/.eclipse/plugins/`
- [ ] **Custom command registration** — users add their own commands
- [ ] **Themes** — color scheme support
- [ ] **Config file** — per-user settings, aliases, colors

---

## Long-Term Ideas

### Distribution
- [ ] **PyInstaller build** — single `.exe` for Windows, no Python install needed
- [ ] **.deb / .rpm packages** for Linux
- [ ] **Docker image** for containerized use
- [ ] **Homebrew formula** for macOS
- [ ] **Android APK** — package with Termux for mobile users

### Community
- [ ] **Contribution guidelines**
- [ ] **Issue templates**
- [ ] **YouTube demos** of new features
- [ ] **Feature request tracker**

### Expansion
- [ ] **File manager TUI** — visual file browser
- [ ] **Multi-language support** — UI in Russian, Spanish, etc.
- [ ] **Help pages with examples** — `man` shows real usage examples

### Monetization (if pursued)
- [ ] Free community edition (current)
- [ ] **Pro edition** — extra features, priority support
- [ ] **Custom builds** for businesses
- [ ] **Support tiers** — paid help for users

---

## Version Timeline

| Version | Status | Focus |
|---|---|---|
| v0.1.0 | ✅ Done | Foundation |
| v0.2.0 | ✅ Done | Shell features |
| v0.3.0 | ✅ Done | Command expansion |
| v0.3.1 | ✅ Done | Bug fixes |
| v0.4.0 | ✅ Done | Major command expansion |
| v0.5.0 | ✅ Done | History, aliases, tab completion, 20 new commands |
| **v0.6.2** | ✅ **Current** | **Pipe engine fix, 22 dev commands, categorized help** |
| v0.6.x | Planned | Polish, testing |
| v0.7.0 | Planned | Power user features |
| v0.8.0 | Planned | Scripting |
| v0.9.0 | Planned | Extensibility |
| v1.0.0 | Planned | Stable release |

---

## Command Count by Version

| Version | Commands |
|---|---|
| v0.1.0 | ~30 ✅ |
| v0.2.0 | ~50 ✅ |
| v0.3.0 | ~80 ✅ |
| v0.3.1 | ~100 ✅ |
| v0.4.0 | ~150 ✅ |
| v0.5.0 | 170 ✅ |
| **v0.6.2** | **180** ✅ |
| v1.0.0 (target) | 200+ |

---

## Notes

- **Versioning** follows semantic versioning (MAJOR.MINOR.PATCH)
- **Breaking changes** reserved for major versions
- **Status codes**: indev / alpha / beta / stable
- **Current status**: indev (in development)

---

## Contributing

Eclipse Shell is a personal project but feedback is welcome:
- **Contact**: YouTube: https://youtube.com/@ilikehamandcheese11 | Telegram: t.me/ilikehamandcheese11
- **Issues**: Open a GitHub issue for bugs or feature requests
- **License**: Proprietary — see LICENSE file
