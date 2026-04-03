# Installing the `llama` CLI

The `llama` CLI is a lightweight management script for interacting with a llama-swap server. It supports health checks, model listing, test prompts, benchmarking, service restarts, and kubectl-style context switching.

---

## macOS / Linux

```bash
# Copy the script
cp llama.sh ~/.local/bin/llama
chmod +x ~/.local/bin/llama

# Ensure ~/.local/bin is on your PATH (add to ~/.bashrc or ~/.zshrc if not)
export PATH="$HOME/.local/bin:$PATH"
```

Reload your shell or `source ~/.zshrc`, then set up your contexts:

```bash
llama context add local 127.0.0.1:8080
llama context add game 192.168.86.63:8080
llama context add ai 192.168.86.235:8080
llama context local

llama health
llama models
```

---

## Windows (PowerShell)

```powershell
# 1. Copy the script somewhere permanent
Copy-Item llama.ps1 "$HOME\Projects\Inference\llama.ps1"

# 2. Set execution policy (once)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. Add to your PowerShell profile
notepad $PROFILE
```

Add this line to your profile:

```powershell
function llama { & "$HOME\Projects\Inference\llama.ps1" @args }
```

Open a new PowerShell window, then set up your contexts:

```powershell
llama context add local 127.0.0.1:8080
llama context add game 192.168.86.63:8080
llama context add ai 192.168.86.235:8080
llama context local

llama health
llama models
```

---

## Context Management

Contexts work like `kubectl config` / `kubectx`. Named server endpoints are stored in `~/.config/llama/config.json` and persist across sessions.

```bash
# Add contexts
llama context add game 192.168.86.63:8080
llama context add ai 192.168.86.235:8080

# Switch context
llama context game
# Switched to context "game" (192.168.86.63:8080)

# List contexts (* = active)
llama context
#   ai           192.168.86.235:8080
# * game         192.168.86.63:8080
#   local        127.0.0.1:8080

# Remove a context
llama context rm old-server

# Override with env var (per-command, ignores active context)
LLAMA_HOST="10.0.0.5:8080" llama health
```

### Resolution order

1. `LLAMA_HOST` env var (if set, overrides everything)
2. Active context from `~/.config/llama/config.json`
3. Error if neither is available

### Config file location

`~/.config/llama/config.json`:
```json
{
  "current": "game",
  "contexts": {
    "game": { "host": "192.168.86.63:8080" },
    "ai": { "host": "192.168.86.235:8080" },
    "local": { "host": "127.0.0.1:8080" }
  }
}
```

---

## Commands Reference

| Command | Description |
|---------|-------------|
| `llama health` | Check if llama-swap is running |
| `llama status` | Show currently loaded model |
| `llama models` | List available models |
| `llama test <model>` | Send a test prompt and show response + speed |
| `llama speed [model]` | Benchmark generation speed (defaults to devstral-small-2) |
| `llama restart` | Restart the llama-swap service (local: nssm/systemctl, remote: SSH) |
| `llama context` | List all contexts |
| `llama context <name>` | Switch active context |
| `llama context add <name> <host:port>` | Add a new context |
| `llama context rm <name>` | Remove a context |

---

## Requirements

- **bash version:** `curl`, `python3`
- **PowerShell version:** PowerShell 5.1+ (built into Windows)
