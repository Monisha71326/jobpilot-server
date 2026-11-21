#!/usr/bin/env bash
# Recommends a free local Ollama model for THIS computer (Linux / macOS / WSL). Nothing is installed or sent anywhere.
set -u
os=$(uname -s)
if [ "$os" = "Darwin" ]; then
  ram_gb=$(( $(sysctl -n hw.memsize) / 1073741824 )); cpus=$(sysctl -n hw.ncpu)
  gpu=$(system_profiler SPDisplaysDataType 2>/dev/null | grep -m1 "Chipset Model" | sed 's/.*: //')
  [ "$(uname -m)" = "arm64" ] && gpu="${gpu:-Apple Silicon} (unified memory)"
else
  ram_gb=$(awk '/MemTotal/ {printf "%d", $2/1048576}' /proc/meminfo); cpus=$(nproc)
  gpu=$(command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
fi
free_gb=$(df -Pk . | awk 'NR==2 {printf "%d", $4/1048576}')
echo "RAM: ${ram_gb} GB | CPU threads: ${cpus} | Free disk here: ${free_gb} GB | GPU: ${gpu:-none detected (CPU inference)}"
echo
if   [ "$ram_gb" -lt 4 ];  then m="";             note="Under 4 GB RAM: a local model will be slow or fail. Use rules-only mode: set OLLAMA_ENABLED=false. Every feature still works with deterministic logic."
elif [ "$ram_gb" -lt 8 ];  then m="llama3.2:3b";  note="4-8 GB RAM: llama3.2:3b (~2 GB download). If it is too slow try llama3.2:1b."
elif [ "$ram_gb" -lt 16 ]; then m="llama3.2:3b";  note="8-16 GB RAM: llama3.2:3b is fast on CPU. If you have a GPU or Apple Silicon, qwen2.5:7b or llama3.1:8b (~5 GB) give better writing."
else                            m="llama3.1:8b";  note="16+ GB RAM: llama3.1:8b or qwen2.5:7b run well; larger models need a GPU."
fi
echo "$note"
[ "$free_gb" -lt 6 ] && [ -n "$m" ] && echo "WARNING: under 6 GB free disk. Models are 1-5 GB; free some space first."
if [ -n "$m" ]; then
  echo; echo "Install (free):"
  echo "  1. Ollama:  https://ollama.com/download   (Linux: curl -fsSL https://ollama.com/install.sh | sh)"
  echo "  2. ollama pull $m"
  echo "  3. In backend/.env set:  OLLAMA_ENABLED=true  OLLAMA_MODEL=$m"
  echo "  4. Optional embeddings: ollama pull nomic-embed-text  and set OLLAMA_EMBED_MODEL=nomic-embed-text"
  echo "Sizes are approximate. Check with 'ollama show $m' and the licence on ollama.com/library before use."
fi
