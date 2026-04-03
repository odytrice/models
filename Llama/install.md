# Installing the `llama` CLI

The `llama` CLI is a lightweight management script for interacting with a llama-swap server. It supports health checks, model listing, test prompts, benchmarking, and service restarts.

It uses the `LLAMA_HOST` environment variable (`host:port`) to target a server.

---

## macOS / Linux

```bash
# Copy the script
cp llama.sh ~/.local/bin/llama
chmod +x ~/.local/bin/llama

# Ensure ~/.local/bin is on your PATH (add to ~/.bashrc or ~/.zshrc if not)
export PATH="$HOME/.local/bin:$PATH"

# Set your server target (add to ~/.bashrc or ~/.zshrc)
export LLAMA_HOST="192.168.86.63:8080"
```

Reload your shell or `source ~/.zshrc`, then:

```bash
llama health
llama models
llama test devstral-small-2
```

### Targeting multiple servers

Set `LLAMA_HOST` per-command or use shell aliases:

```bash
# Per-command
LLAMA_HOST="192.168.86.235:8080" llama models

# Or add aliases to your shell rc
alias llama-game='LLAMA_HOST="192.168.86.63:8080" llama'
alias llama-ai='LLAMA_HOST="192.168.86.235:8080" llama'
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

Add these lines to your profile:

```powershell
$env:LLAMA_HOST = "127.0.0.1:8080"
function llama { & "$HOME\Projects\Inference\llama.ps1" @args }
```

Open a new PowerShell window, then:

```powershell
llama health
llama models
llama test devstral-small-2
```

### Targeting multiple servers

```powershell
# Per-command
$env:LLAMA_HOST = "192.168.86.235:8080"; llama models

# Or add functions to your profile
function llama-game { $env:LLAMA_HOST = "192.168.86.63:8080"; & "$HOME\Projects\Inference\llama.ps1" @args }
function llama-ai { $env:LLAMA_HOST = "192.168.86.235:8080"; & "$HOME\Projects\Inference\llama.ps1" @args }
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

---

## Requirements

- **bash version:** `curl`, `python3`
- **PowerShell version:** PowerShell 5.1+ (built into Windows)
