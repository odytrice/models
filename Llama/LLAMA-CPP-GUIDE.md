# llama.cpp + llama-swap Inference Guide

A complete guide to running local LLM inference using **llama.cpp** and **llama-swap** on any platform. This stack replaces Ollama with direct GGUF model loading, full control over VRAM allocation, and an OpenAI-compatible API.

## Why llama.cpp + llama-swap over Ollama?

| Feature | Ollama | llama.cpp + llama-swap |
|---------|--------|----------------------|
| Model format | Imports into proprietary blob store | Direct GGUF files from HuggingFace |
| API | Ollama API + partial OpenAI compat | Native OpenAI-compatible API |
| VRAM control | Limited (`num_ctx`, `num_gpu`) | Full control (`--ctx-size`, `--n-gpu-layers`, `--parallel`, `--cache-type-k/v`) |
| Flash attention | Env var, not always reliable | Built-in, always available |
| KV cache quant | Global env var | Per-model in config |
| Multi-model | All loaded, competing for VRAM | One at a time, auto-swap with TTL unloading |
| Context gotchas | Defaults to 4096, silently | Explicit in config, no surprises |

---

## Architecture

```
                    ┌──────────────┐
  Client requests   │  llama-swap  │  :8080  (OpenAI-compatible proxy)
  ─────────────────>│              │
                    │  Routes by   │
                    │  model name  │
                    └──────┬───────┘
                           │ starts/stops
                    ┌──────▼───────┐
                    │ llama-server │  :9001  (inference engine + Web UI)
                    │              │
                    │  Loads GGUF  │
                    │  Uses GPU    │
                    └──────────────┘
```

- **llama-server** — the inference engine from llama.cpp. Loads one GGUF model, serves an OpenAI-compatible API, includes a built-in web UI.
- **llama-swap** — a lightweight proxy that sits in front of llama-server. Routes requests by model name, auto-starts the right llama-server process, and kills idle ones after a configurable TTL.
- **Service manager** — systemd (Linux), NSSM (Windows), or launchd (macOS) keeps llama-swap running.
- **`llama` CLI** — a management script (bash or PowerShell) for health checks, testing, benchmarking, and restarting.

---

## Prerequisites

| Platform | GPU | Requirements |
|----------|-----|-------------|
| Linux (NVIDIA) | CUDA | NVIDIA driver 535+, CUDA toolkit 12.x+ |
| Linux (AMD) | Vulkan | Mesa 24.x+, `vulkan-tools`, user in `render`+`video` groups |
| Windows (NVIDIA) | CUDA | NVIDIA driver 560+, no separate CUDA install needed (bundled DLLs) |
| Windows (AMD) | Vulkan | AMD Adrenalin drivers |
| macOS | Metal | macOS 14+ (Metal support is built-in) |

All platforms: `curl`, `python3` (for CLI script JSON parsing).

---

## Server Setup: Linux (NVIDIA CUDA)

### 1. Install GPU drivers

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y nvidia-driver-560 nvidia-utils-560

# Verify
nvidia-smi
```

### 2. Install llama.cpp

#### Option A: Pre-built binary (recommended)

Download the latest release from https://github.com/ggml-org/llama.cpp/releases

```bash
# Find your CUDA version
nvidia-smi  # check "CUDA Version" in top-right

# Download matching build (example: CUDA 12.4, adjust version as needed)
LLAMA_VERSION="b8642"
curl -L -o llama.tar.gz "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_VERSION}/llama-${LLAMA_VERSION}-bin-ubuntu-x64-cuda-12.4-full.tar.gz"
mkdir -p ~/Projects/llama-cpp
tar xzf llama.tar.gz -C ~/Projects/llama-cpp --strip-components=1
rm llama.tar.gz
```

#### Option B: Build from source

```bash
sudo apt install -y build-essential cmake libcurl4-openssl-dev

git clone https://github.com/ggml-org/llama.cpp ~/Projects/llama.cpp
cd ~/Projects/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j $(nproc)
```

Binary at: `build/bin/llama-server`

### 3. Install llama-swap

```bash
# Download latest release
SWAP_VERSION="199"
curl -L -o llama-swap.tar.gz "https://github.com/mostlygeek/llama-swap/releases/download/v${SWAP_VERSION}/llama-swap_${SWAP_VERSION}_linux_amd64.tar.gz"
tar xzf llama-swap.tar.gz -C ~/Projects/ llama-swap
rm llama-swap.tar.gz
chmod +x ~/Projects/llama-swap
```

### 4. Download models

Download GGUF files from HuggingFace. Example:

```bash
mkdir -p ~/Models/devstral-small-2
cd ~/Models/devstral-small-2
curl -L -O "https://huggingface.co/bartowski/Devstral-Small-2-24B-GGUF/resolve/main/Devstral-Small-2-24B-Q4_K_M.gguf"
```

Or use `huggingface-cli`:

```bash
pip install huggingface-hub
huggingface-cli download bartowski/Devstral-Small-2-24B-GGUF Devstral-Small-2-24B-Q4_K_M.gguf --local-dir ~/Models/devstral-small-2
```

### 5. Create llama-swap config

```bash
cat > ~/Projects/llama-swap-config.yaml << 'EOF'
healthCheckTimeout: 300
globalTTL: 300  # Auto-unload after 5 min idle

models:
  devstral-small-2:
    cmd: /home/user/Projects/llama-cpp/build/bin/llama-server -m /home/user/Models/devstral-small-2/Devstral-Small-2-24B-Q4_K_M.gguf --host 0.0.0.0 --port 9001 --n-gpu-layers 99 --flash-attn on --ctx-size 262144 --parallel 1 --cache-type-k q4_0 --cache-type-v q4_0 --jinja
    proxy: http://127.0.0.1:9001
EOF
```

Adjust paths and add more models as needed.

### 6. Set up as systemd service

```bash
sudo tee /etc/systemd/system/llama-swap.service << EOF
[Unit]
Description=llama-swap Model Proxy
After=network-online.target

[Service]
ExecStart=/home/user/Projects/llama-swap -config /home/user/Projects/llama-swap-config.yaml -listen 0.0.0.0:8080
User=$USER
Group=$USER
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable llama-swap
sudo systemctl start llama-swap
```

### 7. Open firewall

```bash
# UFW
sudo ufw allow 8080/tcp

# Or firewalld
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

### 8. Verify

```bash
curl http://localhost:8080/health
# Expected: OK

curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"devstral-small-2","messages":[{"role":"user","content":"Hello"}],"max_tokens":50}'
```

---

## Server Setup: Linux (AMD Vulkan)

Same as NVIDIA setup above, with these differences:

**Step 1: Drivers**
```bash
sudo apt install -y mesa-vulkan-drivers vulkan-tools
sudo usermod -aG render,video $USER
# Log out and back in

# Verify
vulkaninfo --summary
```

**Step 2: Build llama.cpp with Vulkan**
```bash
sudo apt install -y libvulkan-dev
cmake -B build -DGGML_VULKAN=ON -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j $(nproc)
```

For AMD unified memory systems (e.g., Ryzen AI MAX), expand GPU-accessible memory:
```bash
# /etc/default/grub
GRUB_CMDLINE_LINUX_DEFAULT="... amdgpu.gttsize=122880"
# Then: sudo update-grub && reboot
```

---

## Server Setup: Windows

### 1. Install llama-swap

```powershell
winget install llama-swap
```

### 2. Install llama.cpp (CUDA build)

**Important:** `winget install ggml.llamacpp` installs the Vulkan build. For NVIDIA GPUs, download the CUDA build manually.

```powershell
# Check your CUDA version
nvidia-smi   # look at "CUDA Version" top-right

# Download CUDA build + runtime DLLs
$version = "b8642"
Invoke-WebRequest -Uri "https://github.com/ggml-org/llama.cpp/releases/download/$version/llama-$version-bin-win-cuda-13.1-x64.zip" -OutFile llama-cuda.zip
Invoke-WebRequest -Uri "https://github.com/ggml-org/llama.cpp/releases/download/$version/cudart-llama-bin-win-cuda-13.1-x64.zip" -OutFile cudart.zip

# Extract
$dest = "$HOME\Projects\Inference\llama-cpp"
New-Item -ItemType Directory -Force -Path $dest
Expand-Archive llama-cuda.zip -DestinationPath $dest -Force
Expand-Archive cudart.zip -DestinationPath $dest -Force
Remove-Item llama-cuda.zip, cudart.zip
```

### 3. Download models

```powershell
pip install huggingface-hub
huggingface-cli download bartowski/Devstral-Small-2-24B-GGUF Devstral-Small-2-24B-Q4_K_M.gguf --local-dir $HOME\.models\devstral-small-2
```

### 4. Create llama-swap config

Create `$HOME\Projects\Inference\llama-swap\config.yaml`:

```yaml
healthCheckTimeout: 300
globalTTL: 300

models:
  devstral-small-2:
    cmd: cmd /c "cd /d C:\Users\YOU\Projects\Inference\llama-cpp && llama-server.exe -m C:\Users\YOU\.models\devstral-small-2\Devstral-Small-2-24B-Q4_K_M.gguf --host 0.0.0.0 --port 9001 --n-gpu-layers 99 --flash-attn on --ctx-size 262144 --parallel 1 --cache-type-k q4_0 --cache-type-v q4_0 --jinja"
    proxy: http://127.0.0.1:9001
```

**Why `cmd /c "cd /d ... &&"`?** When NSSM runs llama-swap as SYSTEM, the spawned llama-server.exe can't find its sibling CUDA DLLs (ggml-cuda.dll, cublas64_13.dll, etc.) unless its working directory is set correctly. The `cd /d` wrapper solves this.

### 5. Install NSSM and create service

```powershell
winget install nssm

# Run as Administrator:
nssm install llama-swap "C:\path\to\llama-swap.exe" "-config C:\Users\YOU\Projects\Inference\llama-swap\config.yaml -listen 0.0.0.0:8080"
nssm start llama-swap
```

Service management:
```powershell
nssm stop llama-swap
nssm start llama-swap
nssm restart llama-swap
nssm status llama-swap
nssm remove llama-swap confirm   # uninstall
```

### 6. Open firewall

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "llama-swap" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Any
```

### 7. Verify

```powershell
Invoke-RestMethod http://localhost:8080/health
# Expected: OK

$body = '{"model":"devstral-small-2","messages":[{"role":"user","content":"Hello"}],"max_tokens":50}'
Invoke-RestMethod -Uri "http://localhost:8080/v1/chat/completions" -Method Post -ContentType "application/json" -Body $body
```

---

## Server Setup: macOS (Metal)

```bash
# Install via Homebrew
brew install llama.cpp

# llama-swap
curl -L -o /usr/local/bin/llama-swap "https://github.com/mostlygeek/llama-swap/releases/download/v199/llama-swap_199_darwin_arm64"
chmod +x /usr/local/bin/llama-swap

# Config and models follow the same pattern as Linux
# Use --n-gpu-layers 99 for Metal acceleration (automatic on Apple Silicon)
```

For a background service, use launchd:
```bash
# Create ~/Library/LaunchAgents/com.llama-swap.plist
# Or just run in a tmux session
```

---

## Model Selection & Quantization

### Quantization Formats

| Format | Bits/Weight | Quality | VRAM Savings vs f16 |
|--------|-------------|---------|---------------------|
| Q4_K_M | ~4.5 | Good (sweet spot) | ~75% |
| Q5_K_M | ~5.5 | Better | ~65% |
| Q8_0 | 8 | Near-lossless | ~50% |

**Recommendation:** Q4_K_M for most models. It's the best balance of quality and VRAM efficiency.

### KV Cache Quantization

| KV Cache Type | Bits | Quality Impact | Memory vs f16 |
|---------------|------|---------------|----------------|
| f16 (default) | 16 | Baseline | 1x |
| q8_0 | 8 | Negligible loss | 0.5x |
| q4_0 | 4 | Slight degradation at very high context | 0.25x |

Set with `--cache-type-k q4_0 --cache-type-v q4_0`. Requires `--flash-attn on`.

---

## Key llama-server Flags

| Flag | Description | Recommended |
|------|-------------|-------------|
| `--n-gpu-layers 99` | Offload all layers to GPU | Always |
| `--flash-attn on` | Enable flash attention | Always |
| `--ctx-size N` | Context window size in tokens | Set explicitly (see VRAM Budgeting) |
| `--parallel N` | Number of concurrent request slots | `1` for llama-swap (it handles routing) |
| `--cache-type-k q4_0` | Quantize key cache | Use with flash attention |
| `--cache-type-v q4_0` | Quantize value cache | Use with flash attention |
| `--host 0.0.0.0` | Listen on all interfaces | For network access |
| `--port 9001` | Listening port | Match llama-swap proxy config |
| `--jinja` | Enable Jinja2 chat templates | Recommended for proper chat formatting |
| `-m <path>` | Path to GGUF model file | Required |

---

## llama-swap Configuration

```yaml
healthCheckTimeout: 300   # Max seconds to wait for model to load
globalTTL: 300            # Kill idle model after N seconds (0 = never)

models:
  model-name:             # Name used in API requests
    cmd: /path/to/llama-server -m /path/to/model.gguf [flags...]
    proxy: http://127.0.0.1:9001
    ttl: 0                # Optional: override globalTTL for this model
```

**How it works:**
1. Client sends request with `"model": "model-name"`
2. llama-swap checks if that model's llama-server is running
3. If not, it kills any currently running llama-server and starts the new one
4. Waits for health check to pass (up to `healthCheckTimeout` seconds)
5. Proxies the request to llama-server
6. After `TTL` seconds of idle, kills the process to free VRAM

---

## VRAM Budgeting

**Total VRAM = Model Weights + KV Cache + Overhead (~500MB)**

### The `--ctx-size 0` Trap

Setting `--ctx-size 0` tells llama-server to use the model's native maximum context from GGUF metadata. Combined with the default `--parallel 4` (4 concurrent slots), this can allocate an enormous KV cache:

- Devstral Small 2 reports 384K native context
- 4 slots x 384K = 1.5M tokens of KV cache
- Result: VRAM overflows to system RAM, inference slows to a crawl

**Always set `--ctx-size` explicitly and use `--parallel 1`** when running behind llama-swap.

### Context Size Guidelines (Q4_0 KV cache, 1 slot)

| Model Weights | Available VRAM (32GB GPU) | Safe Max Context |
|--------------|--------------------------|-------------------|
| 14 GB | ~17 GB | 256K |
| 16 GB | ~15 GB | 256K |
| 18 GB | ~13 GB | 196K |

For 24GB GPUs, reduce context proportionally.

---

## API Usage

llama-swap exposes an OpenAI-compatible API on port 8080.

### Chat Completions

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "devstral-small-2",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

### Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="unused")

response = client.chat.completions.create(
    model="devstral-small-2",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=100,
)
print(response.choices[0].message.content)
```

### Other Endpoints

```bash
# Health check
curl http://localhost:8080/health

# List models
curl http://localhost:8080/v1/models

# Currently running model
curl http://localhost:8080/running
```

---

## Web UI

llama-server includes a built-in chat UI. Access it at:

```
http://localhost:9001
```

The UI is only available while a model is loaded. Send any API request first to trigger loading, then open the browser. The UI disappears when the model is TTL'd out.

For network access, use `http://<server-ip>:9001`.

---

## Management CLI (`llama`)

A management script for interacting with llama-swap from any machine. Available in bash (`llama.sh`) and PowerShell (`llama.ps1`).

```bash
llama health              # Is llama-swap running?
llama status              # What model is loaded?
llama models              # List available models
llama test devstral-small-2  # Send a test prompt
llama speed gemma4-26b    # Benchmark a model
llama restart             # Restart the service
```

Uses the `LLAMA_HOST` environment variable (`host:port`) to target a server. See [install.md](install.md) for setup instructions.

---

## Tips & Troubleshooting

### CUDA vs Vulkan

- **NVIDIA GPUs:** Always use the CUDA build. It's significantly faster than Vulkan on NVIDIA hardware.
- **AMD GPUs:** Use the Vulkan build. CUDA is NVIDIA-only.
- **winget's llama.cpp is Vulkan-only.** For NVIDIA on Windows, download the CUDA build manually from GitHub releases.

### DLL Loading Failure on Windows (NSSM)

When llama-swap runs as an NSSM service under the SYSTEM account, spawned llama-server processes can't find their sibling DLLs (ggml-cuda.dll, etc.). Fix: wrap the command with `cmd /c "cd /d <llama-cpp-dir> && llama-server.exe ..."` in the config.

### Model Spilling to System RAM

Symptoms: extremely slow inference, `nvidia-smi` shows VRAM not fully used or system RAM spiking.

Causes:
1. `--ctx-size 0` with default `--parallel 4` allocates way too much KV cache
2. Model is too large for the GPU

Fix: set `--ctx-size` explicitly, use `--parallel 1`, verify with `nvidia-smi` after loading.

### Model Won't Load (502 from llama-swap)

- Check the model file path in the config
- Check that port 9001 isn't already in use: `ss -tlnp | grep 9001` (Linux) or `netstat -an | findstr 9001` (Windows)
- Check llama-swap logs: `journalctl -u llama-swap -n 30` (Linux)

### Slow Prompt Processing

- Ensure flash attention is enabled (`--flash-attn on`)
- Verify full GPU offload: `nvidia-smi` should show model weights in VRAM
- Check that `--n-gpu-layers 99` is set (offload all layers)

### System RAM Recommendation

64GB+ recommended alongside GPU VRAM. The OS, llama-swap, and model loading all need system RAM beyond what the GPU uses.
