# ship

A lightweight, secure deployment CLI using a Git-like staging model and guardrails to synchronize files and directories to remote servers over SSH and rsync.

---

## Features

- **Git-like Workflow:** Familiar commands (`init`, `add`, `remove`, `status`, `push`).
- **Multi-layer Guardrails:**
  - Path traversal and symlink escape defenses.
  - Automatic blocking of sensitive files (`.env`, `.git/`, `.ssh/`, `.ship/`, private keys).
  - Protection of remote system directories (`/`, `/home`, `/root`, `/etc`, `/var`, `/usr`, `/bin`).
- **Ignore Rules:** Project-level `.shipignore` to exclude dependencies, cache, logs, and build artifacts.
- **Dry-run & Inspection:** Inspect remote directory structures and preview synchronization before applying changes.
- **Zero Dependencies:** Built entirely with Python standard library, standard OpenSSH, and rsync.

---

## Requirements & Setup

### Prerequisites
- Python 3.10+
- OpenSSH client (`ssh`)
- rsync

### Installation

#### Option 1: Shell Alias (Recommended)
Add the following line to your `~/.bashrc` or `~/.zshrc`:

```bash
alias ship="python3 /path/to/ship/main.py"
```

Reload your shell configuration:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

#### Option 2: Symlink to PATH
```bash
mkdir -p ~/.local/bin
ln -sf /path/to/ship/main.py ~/.local/bin/ship
chmod +x /path/to/ship/main.py
```

---

## Architecture

Running `ship init` inside any project directory creates an isolated management workspace:

```text
my-project/
├── .ship/
│   ├── config.env              # SSH connection settings (host, port, user, remote_dir)
│   ├── guardrails/
│   │   ├── allowed             # Regular expressions for permitted remote directories
│   │   ├── deny                # Patterns for sensitive files refused by ship
│   │   └── protected           # Remote system paths protected against deletion/sync
│   └── state/
│       └── files               # Staging manifest of items ready to push
├── .shipignore                 # Exclusion rules (similar to .gitignore)
└── ...
```

---

## Quickstart

### 1. Initialize Workspace
Run `ship init` in your project root:
```bash
ship init
```
Follow the interactive prompts to configure server credentials and remote directory. To skip prompts with default templates, use `ship init --no-input`.

### 2. Verify Environment & Connection
```bash
ship preflight
```
Validates local tools (`ssh`, `rsync`, `python3`), configuration files, and tests SSH connectivity.

### 3. Stage Files
```bash
# Stage entire project
ship add .

# Stage specific files or directories
ship add src/ public/ package.json
```

### 4. Check Staging Status
```bash
ship status
```
Displays the local file tree and currently staged items.

### 5. Inspect Remote Target
```bash
# Inspect remote directory tree (default depth: 2)
ship inspect

# Specify depth
ship inspect 3
```

### 6. Synchronize (Push)
```bash
# Dry-run preview
ship push -n

# Synchronize staged files to remote server
ship push

# Verbose mode with transfer progress
ship push -v
```

### 7. Unstage or Clean
```bash
# Unstage specific paths
ship remove src/temp.py

# Clear entire staging area
ship remove --all

# Clean remote destination directory (guarded)
ship clean -n   # Dry-run
ship clean      # Interactive confirmation
ship clean -y   # Skip confirmation
```

---

## Command Reference

| Command | Description | Common Flags |
| :--- | :--- | :--- |
| `ship init` | Initialize `.ship/` workspace and `.shipignore` | `--no-input` |
| `ship preflight` | Check environment tools and test SSH connection | |
| `ship add <paths...>` | Stage files or directories for deployment | |
| `ship remove <paths...>` | Remove paths from staging manifest | `--all` |
| `ship status` | View workspace structure and staged files | `-L <depth>` |
| `ship inspect [depth]` | Inspect remote directory tree | `depth` (default: 2) |
| `ship push` | Synchronize staged items to remote server | `-n` (dry-run), `-v` (verbose) |
| `ship clean` | Delete remote destination folder | `-n` (dry-run), `-y` (yes) |

---

## Guardrails & Policies

- **`.shipignore`**: Excludes transient files, build outputs, and dependencies (`node_modules/`, `venv/`, `.cache/`).
- **`.ship/guardrails/allowed`**: Enforces permitted `REMOTE_DIR` targets (defaults to `/home/<user>/<project>(/.*)?`).
- **`.ship/guardrails/deny`**: Hard block on staging or pushing secrets (`.env`, `*.env`, `.ssh/`, `.git/`, `*.pem`, `id_rsa`).
- **`.ship/guardrails/protected`**: Prevents accidental modification or deletion of critical root paths (`/`, `/home`, `/root`, `/etc`, `/var`, `/usr`, `/bin`).

---

## Testing

Run the automated test suite:

```bash
# Unit tests
python3 -m unittest discover tests

# Security and regression test suite
bash tests/test_security.sh
```
