"""
Test: does /api/generate return logprobs for cloud models?
A comment suggested logprobs only work via /api/generate, not /api/chat.
"""

import httpx
import json
import time

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

payload = {
    "model": "glm-5:cloud",
    "prompt": "What is 2 + 2? Answer in one word.",
    "stream": False,
    "logprobs": True,
    "top_logprobs": 5,
    "options": {
        "temperature": 0.7,
        "top_p": 0.95,
        "num_predict": 512,
    },
}

print(f"Sending to {OLLAMA_GENERATE_URL} with model glm-5:cloud ...")
print(f"Payload:\n{json.dumps(payload, indent=2)}\n")

start = time.monotonic()
response = httpx.post(OLLAMA_GENERATE_URL, json=payload, timeout=120.0)
elapsed = time.monotonic() - start

print(f"Status: {response.status_code}")
print(f"Time: {elapsed:.1f}s\n")

data = response.json()

with open("logprob_test_cloud_generate.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("Full response saved to: logprob_test_cloud_generate.json")

# Check for logprobs
has_logprobs = "logprobs" in data and data["logprobs"]
print(f"\n'logprobs' key present: {'logprobs' in data}")
print(f"'logprobs' has data:    {has_logprobs}")

if has_logprobs:
    lp = data["logprobs"]
    print(f"Number of tokens:       {len(lp)}")
    print(f"\nFirst 3 token entries:")
    for entry in lp[:3]:
        tok = entry.get("token", "")
        prob = entry.get("logprob", "")
        alts = [t["token"] for t in entry.get("top_logprobs", [])[:3]]
        print(f"  token={tok!r:20s}  logprob={prob:.4f}  top_alts={alts}")
else:
    print("\nNo logprobs returned.")
    print(f"Response keys: {list(data.keys())}")
    content = data.get("response", "")
    print(f"Response content: {content[:200]}")
