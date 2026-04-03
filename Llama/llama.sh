#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LLAMA_HOST:-}" ]]; then
    echo "LLAMA_HOST not set. Export it as host:port, e.g.:" >&2
    echo '  export LLAMA_HOST="127.0.0.1:8080"' >&2
    exit 1
fi

BASE="http://$LLAMA_HOST"
HOST_IP="${LLAMA_HOST%%:*}"

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
            echo "$LLAMA_HOST: unreachable" >&2
        fi
        ;;

    status)
        curl -sf "$BASE/running" --max-time 5 | python3 -m json.tool 2>/dev/null || \
            echo "$LLAMA_HOST: unreachable" >&2
        ;;

    test)
        if [[ -z "$model" ]]; then
            echo "Usage: llama test <model>" >&2
            exit 1
        fi
        echo "Loading $model on $LLAMA_HOST..."
        response=$(curl -sf "$BASE/v1/chat/completions" --max-time 120 \
            -H "Content-Type: application/json" \
            -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"Write a haiku about coding.\"}],\"max_tokens\":100}")

        content=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['choices'][0]['message']['content'])")
        prompt_tok=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['usage']['prompt_tokens'])")
        comp_tok=$(echo "$response" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['usage']['completion_tokens'])")

        echo ""
        echo "$content"
        echo ""
        echo "Tokens: $prompt_tok prompt + $comp_tok completion"

        # Print speed if timings are available
        echo "$response" | python3 -c "
import sys, json
r = json.load(sys.stdin)
t = r.get('timings', {})
if t:
    print(f\"Speed: {t['prompt_per_second']:.1f} tok/s prompt, {t['predicted_per_second']:.1f} tok/s generation\")
" 2>/dev/null || true
        ;;

    speed)
        model="${model:-devstral-small-2}"
        echo "Benchmarking $model on $LLAMA_HOST..."
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

    models)
        curl -sf "$BASE/v1/models" --max-time 5 | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(f'Models on $LLAMA_HOST:')
for m in r['data']:
    print(f'  - {m[\"id\"]}')
" 2>/dev/null || echo "$LLAMA_HOST: unreachable" >&2
        ;;

    *)
        echo "Usage: llama <command> [model]"
        echo ""
        echo "Commands:"
        echo "  health           Check if llama-swap is running"
        echo "  status           Show currently loaded model"
        echo "  test <model>     Send a test prompt"
        echo "  speed [model]    Benchmark generation speed"
        echo "  restart          Restart the llama-swap service"
        echo "  models           List available models"
        echo ""
        echo 'Requires: export LLAMA_HOST="host:port"'
        ;;
esac
