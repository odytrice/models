#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${HOME}/.config/llama"
CONFIG_FILE="${CONFIG_DIR}/config.json"

# --- Config helpers ---
read_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        cat "$CONFIG_FILE"
    else
        echo '{"current":"","contexts":{}}'
    fi
}

save_config() {
    mkdir -p "$CONFIG_DIR"
    echo "$1" > "$CONFIG_FILE"
}

get_field() {
    echo "$1" | python3 -c "import sys,json; print(json.load(sys.stdin)$2)" 2>/dev/null
}

# --- Handle context command before resolving host ---
if [[ "${1:-}" == "context" ]]; then
    cfg=$(read_config)
    sub="${2:-}"

    if [[ -z "$sub" ]]; then
        # List contexts
        python3 -c "
import json, sys
cfg = json.load(sys.stdin)
contexts = cfg.get('contexts', {})
current = cfg.get('current', '')
if not contexts:
    print('No contexts configured. Add one with: llama context add <name> <host:port>')
    sys.exit(0)
for name in sorted(contexts):
    marker = '*' if name == current else ' '
    host = contexts[name]['host']
    print(f'{marker} {name:<12} {host}')
" <<< "$cfg"
        exit 0
    fi

    if [[ "$sub" == "add" ]]; then
        name="${3:?Usage: llama context add <name> <host:port>}"
        host="${4:?Usage: llama context add <name> <host:port>}"
        cfg=$(python3 -c "
import json, sys
cfg = json.load(sys.stdin)
cfg.setdefault('contexts', {})['$name'] = {'host': '$host'}
if not cfg.get('current'):
    cfg['current'] = '$name'
print(json.dumps(cfg, indent=2))
" <<< "$cfg")
        save_config "$cfg"
        echo "Added context \"$name\" ($host)"
        exit 0
    fi

    if [[ "$sub" == "rm" ]]; then
        name="${3:?Usage: llama context rm <name>}"
        cfg=$(python3 -c "
import json, sys
cfg = json.load(sys.stdin)
cfg.get('contexts', {}).pop('$name', None)
if cfg.get('current') == '$name':
    cfg['current'] = ''
print(json.dumps(cfg, indent=2))
" <<< "$cfg")
        save_config "$cfg"
        echo "Removed context \"$name\""
        exit 0
    fi

    # Switch context: llama context <name>
    target="$sub"
    host=$(get_field "$cfg" "['contexts']['$target']['host']" 2>/dev/null || true)
    if [[ -z "$host" ]]; then
        echo "Unknown context \"$target\". Available:" >&2
        python3 -c "
import json, sys
cfg = json.load(sys.stdin)
for name, v in cfg.get('contexts', {}).items():
    print(f'  {name}  {v[\"host\"]}')
" <<< "$cfg" >&2
        exit 1
    fi
    cfg=$(python3 -c "
import json, sys
cfg = json.load(sys.stdin)
cfg['current'] = '$target'
print(json.dumps(cfg, indent=2))
" <<< "$cfg")
    save_config "$cfg"
    echo "Switched to context \"$target\" ($host)"
    exit 0
fi

# --- Resolve host: env var > config file ---
CONTEXT_NAME=""
if [[ -n "${LLAMA_HOST:-}" ]]; then
    RESOLVED_HOST="$LLAMA_HOST"
else
    cfg=$(read_config)
    current=$(get_field "$cfg" "['current']" || true)
    if [[ -n "$current" ]]; then
        host=$(get_field "$cfg" "['contexts']['$current']['host']" 2>/dev/null || true)
        if [[ -n "$host" ]]; then
            CONTEXT_NAME="$current"
            RESOLVED_HOST="$host"
        fi
    fi
fi

if [[ -z "${RESOLVED_HOST:-}" ]]; then
    echo "No active context. Set one up:" >&2
    echo '  llama context add local 127.0.0.1:8080' >&2
    echo '  llama context local' >&2
    echo "" >&2
    echo "Or set LLAMA_HOST directly:" >&2
    echo '  export LLAMA_HOST="127.0.0.1:8080"' >&2
    exit 1
fi

if [[ -n "$CONTEXT_NAME" ]]; then
    LABEL="$CONTEXT_NAME ($RESOLVED_HOST)"
else
    LABEL="$RESOLVED_HOST"
fi

BASE="http://$RESOLVED_HOST"
HOST_IP="${RESOLVED_HOST%%:*}"

# Detect if the target is the local machine
is_local() {
    [[ "$HOST_IP" == "127.0.0.1" || "$HOST_IP" == "localhost" ]] && return 0
    local local_ips
    if command -v ip &>/dev/null; then
        local_ips=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
    elif command -v ifconfig &>/dev/null; then
        local_ips=$(ifconfig | grep -oE 'inet\s+\d+(\.\d+){3}' | awk '{print $2}')
    fi
    echo "$local_ips" | grep -qx "$HOST_IP"
}

cmd="${1:-}"
model="${2:-}"

case "$cmd" in
    health)
        if curl -sf "$BASE/health" --max-time 5; then
            echo ""
        else
            echo "$LABEL: unreachable" >&2
        fi
        ;;

    status)
        running=$(curl -sf "$BASE/running" --max-time 5 2>/dev/null) || {
            echo "$LABEL: unreachable" >&2; exit 1
        }
        echo "$running" | python3 -m json.tool

        # If a model is loaded, show its server config
        props=$(curl -sf "$BASE/props" --max-time 5 2>/dev/null) && \
            echo "$props" | python3 -c "
import sys, json
p = json.load(sys.stdin)
dgs = p.get('default_generation_settings', {})
n_ctx = dgs.get('n_ctx')
if n_ctx:
    ctx = f'{n_ctx:,} ({n_ctx // 1024}K)' if n_ctx >= 1024 else f'{n_ctx:,}'
    print(f'Context:       {ctx} tokens')
total = p.get('total_slots')
if total: print(f'Parallel:      {total}')
for lbl, k in [('Cache (K)', 'cache_type_k'), ('Cache (V)', 'cache_type_v')]:
    v = p.get(k) or dgs.get(k)
    if v: print(f'{lbl}:     {v}')
" 2>/dev/null || true
        ;;

    test)
        if [[ -z "$model" ]]; then
            echo "Usage: llama test <model>" >&2
            exit 1
        fi
        echo "Loading $model on $LABEL..."
        response=$(curl -sf "$BASE/v1/chat/completions" --max-time 120 \
            -H "Content-Type: application/json" \
            -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"Write a haiku about coding.\"}],\"max_tokens\":100}")

        echo "$response" | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(f\"\n{r['choices'][0]['message']['content']}\")
print(f\"\nTokens: {r['usage']['prompt_tokens']} prompt + {r['usage']['completion_tokens']} completion\")
t = r.get('timings', {})
if t:
    print(f\"Speed: {t['prompt_per_second']:.1f} tok/s prompt, {t['predicted_per_second']:.1f} tok/s generation\")
"
        ;;

    speed)
        model="${model:-devstral-small-2}"
        echo "Benchmarking $model on $LABEL..."
        prompt="Write a detailed explanation of how a CPU pipeline works, including fetch, decode, execute, memory access, and writeback stages. Include examples of pipeline hazards and how modern processors handle them."
        response=$(curl -sf "$BASE/v1/chat/completions" --max-time 300 \
            -H "Content-Type: application/json" \
            -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"$prompt\"}],\"max_tokens\":500}")

        echo "$response" | python3 -c "
import sys, json
r = json.load(sys.stdin)
t = r.get('timings', {})
u = r['usage']
if t:
    print(f\"\nResults:\")
    print(f\"  Prompt:     {t['prompt_per_second']:.1f} tok/s ({u['prompt_tokens']} tokens)\")
    print(f\"  Generation: {t['predicted_per_second']:.1f} tok/s ({u['completion_tokens']} tokens)\")
else:
    print(f\"\nTokens: {u['prompt_tokens']} prompt + {u['completion_tokens']} completion\")
"
        ;;

    restart)
        if is_local; then
            echo "Restarting llama-swap service locally..."
            sudo systemctl restart llama-swap
        else
            echo "Restarting llama-swap on $HOST_IP via SSH..."
            ssh "$HOST_IP" "sudo systemctl restart llama-swap"
            echo "Done."
        fi
        ;;

    info)
        if [[ -z "$model" ]]; then
            echo "Usage: llama info <model>" >&2
            exit 1
        fi
        echo "Loading $model on $LABEL..."
        props=$(curl -sf "$BASE/upstream/$model/props" --max-time 120) || {
            echo "Failed to load $model" >&2; exit 1
        }
        echo "$props" | python3 -c "
import sys, json
p = json.load(sys.stdin)
dgs = p.get('default_generation_settings', {})
print(f'Model:         $model')
n_ctx = dgs.get('n_ctx')
if n_ctx:
    ctx = f'{n_ctx:,} ({n_ctx // 1024}K)' if n_ctx >= 1024 else f'{n_ctx:,}'
    print(f'Context:       {ctx} tokens')
total = p.get('total_slots')
if total: print(f'Parallel:      {total}')
for lbl, k in [('Cache (K)', 'cache_type_k'), ('Cache (V)', 'cache_type_v')]:
    v = p.get(k) or dgs.get(k)
    if v: print(f'{lbl}:     {v}')
model_path = p.get('model_path', '')
if model_path:
    print(f'Model path:    {model_path}')
"
        ;;

    models)
        curl -sf "$BASE/v1/models" --max-time 5 | python3 -c "
import sys, json
r = json.load(sys.stdin)
print('Models on $LABEL:')
for m in r['data']:
    print(f'  - {m[\"id\"]}')
" 2>/dev/null || echo "$LABEL: unreachable" >&2
        ;;

    *)
        echo "Usage: llama <command> [args]"
        echo ""
        echo "Commands:"
        echo "  health              Check if llama-swap is running"
        echo "  status              Show currently loaded model + config"
        echo "  info <model>        Show model config (context, cache, etc.)"
        echo "  test <model>        Send a test prompt"
        echo "  speed [model]       Benchmark generation speed"
        echo "  restart             Restart the llama-swap service"
        echo "  models              List available models"
        echo ""
        echo "Context management:"
        echo "  context             List all contexts"
        echo "  context <name>      Switch active context"
        echo "  context add <name> <host:port>"
        echo "  context rm <name>"
        ;;
esac
