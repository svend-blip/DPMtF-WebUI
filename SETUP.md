# DPMtF-WebUI Installation Guide

This guide walks you through installing and setting up the DPMtF-WebUI project on a fresh machine.

## System Requirements

- Python 3.12
- CUDA 13.0
- tmux
- SQLite 3
- **NVIDIA GPU with sufficient VRAM for at least one role model** (see below)

### Hardware and Models

The DPMtF-WebUI autonomous flow uses three distinct models, one per role:

| Alias | Role | VRAM Required | Notes |
|-------|------|---------------|-------|
| `laguna-local` | supervisor01_llama | ~29 GB | MoE model; offloads via `--n-cpu-moe 31`, consuming ~37 GB host memory. Context: 262144 tokens, one slot. |
| `imple-fast` | imple01SG | ~20 GB | `qwen3.6:27b-q4_K_M`, full GPU residency. |
| `review02-local` | review01SG | ~22 GB | `qwen3.6:35b-a3b-64k`, full GPU residency. |

**mcp-light is a mandatory prerequisite.** The LLAMASG cold-start procedure directs every framework question to mcp-light (`get_flow_steps`, `get_governance_file`). A role that wakes without it silently falls back to reading source, which costs significant time. Install and start mcp-light *before* your first dispatch, not after a role has already woken up:

1. Clone the repository (see Clone Repositories section below) and check out `main`.
2. Install the systemd unit: copy `mcp-light.service` to `/etc/systemd/system/`, enable it at boot.
3. **Unit-file discrepancy:** the unit file shipped in the repo declares `ExecStart=/usr/bin/python3 …` while a working installation uses the virtual-environment interpreter (`…/venv/bin/python …`). Copying the repo's verbatim line produces a service that starts under system Python without the venv's dependencies and will fail at runtime. Always use the venv path for `ExecStart`.
4. Verify: `curl -s http://127.0.0.1:9135/mcp` should return MCP transport data.

**The roles are never co-resident.** Dispatch stops the outgoing model, waits for
nvidia-smi to confirm freed memory, and only then loads the incoming model. A 32 GB
GPU is sufficient because at most one model occupies the card at any time — it would
not work with two models loaded simultaneously.

## Clone Repositories

Clone all three repositories as siblings under your projects base directory (default: $HOME):

```bash
cd $HOME
git clone https://github.com/your-org/DPMtF-WebUI.git
git clone https://github.com/your-org/model-allocator.git
git clone https://github.com/svend-blip/mcp-light.git
```

> Note: Replace `your-org` with the actual organization name if different. The layout should be:
> ```
> $HOME/
>   ├── DPMtF-WebUI/
>   ├── model-allocator/
>   └── mcp-light/
> ```

## Python Environment

Create and activate a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Environment Configuration

Copy the `.env.example` file to `.env` and configure it:

```bash
cp .env.example .env
```

Edit the `.env` file to set the required environment variables:

- `DPMTF_BRIDGE_DIR`: Bridge directory where bridge flow files are stored
- `DPMTF_HOME_DIR`: Home directory used to resolve other paths
- `DPMTF_PROJECT_ROOT`: Project root directory (should be set to your DPMtF-WebUI directory)
- `DPMTF_MACHINE_PROFILE`: Machine profile filename for determining which machine configuration to load
- `DPMTF_OPENCODE_BIN`: Path to the opencode binary
- `DPMTF_ARCHITECT_SESSION`: Name of the architect session for BridgeV002
- `DPMTF_IMPLEMENTER_SESSION`: Name of the implementer session for BridgeV002
- `DPMTF_REVIEW_SESSION`: Name of the review session for BridgeV002
- `DPMTF_OMITTED_CARD_PATHS`: List of paths to exclude from system dashboard cards
- `DPMTF_TRADE_INBOX`: Path to the Trade Cockpit inbox

### Model Allocator Configuration

The following environment variables are required for model-allocator integration:

- `LLAMA_SERVER_BIN`: Path to the llama-server binary for llama.cpp runtime (Example: `/home/svend/llama.cpp/llama-server`)
- `MODEL_ROOT_GGUF`: Directory containing GGUF model files for llama.cpp runtime (Example: `/home/svend/models/gguf`)
- `MODEL_ROOT_SGLANG`: Directory containing SGLang model repositories (Example: `/home/svend/models/sglang`)
- `SGLANG_VENV_PATH`: Path to the SGLang virtual environment (Example: `/home/svend/sglang-venv`)

## Local Runtime Installations

### llama.cpp (Laguna server)
Install llama.cpp from https://github.com/ggerganov/llama.cpp and build the llama-server binary.
Set `LLAMA_SERVER_BIN` to point to the built binary.

### SGLang venv
Install SGLang in a virtual environment and set `SGLANG_VENV_PATH` to the path of that environment.

### Ollama
Install Ollama from https://ollama.com and ensure it's running.
The DPMtF-WebUI will use Ollama to manage models via the ollama client.
Set `OLLAMA_BASE_URL` environment variable to `http://127.0.0.1:11434` for default Ollama instance.

#### Fetching the Models

Two of the three role models are pulled via Ollama:

```bash
ollama pull qwen3.6:27b-q4_K_M      # imple-fast (imple01SG — Implementer)
ollama pull qwen3.6:35b-a3b-64k     # review02-local (review01SG — Reviewer)
```

The third model, `laguna-local` (supervisor01_llama), is served from a local GGUF
directory using llama.cpp. Download a compatible GGUF file (e.g., Laguna-S 2.1 IQ4_XS),
place it in a directory on your machine, and set `MODEL_ROOT_GGUF` in `.env` to point
to that directory.

### OpenCode
Install OpenCode from https://opencode.ai and set `DPMTF_OPENCODE_BIN` to the path of the opencode executable.

### Claude Code
Install Claude Code from https://claude.ai and ensure it is configured properly.
The DPMtF-WebUI uses Claude Code's built-in OpenAI-compatible API via `claude-code` adapter.

## Database Initialization

Initialize the database using the provided script:

```bash
python scripts/init_db.py
```

## model-allocator Configuration

The model-allocator is a separate repository that needs to be configured:

1. Copy example configuration files:
   ```bash
   cp model-allocator/models.example.yaml model-allocator/models.yaml
   cp model-allocator/runtime_profiles.example.yaml model-allocator/runtime_profiles.yaml
   ```

2. Configure the model-allocator by editing the copied YAML files and setting appropriate environment variables.

## Troubleshooting

### Common First-Install Errors

1. **Python version issues**: Make sure you're using Python 3.12 or higher.
2. **Missing dependencies**: Install all packages listed in `requirements.txt`.
3. **Database initialization errors**: Ensure the database path in `dpmtf.ini` is valid and accessible.
4. **Path resolution issues**: Double-check all environment variable paths are correct and accessible.
5. **Permission denied errors**: Make sure all necessary directories have proper read/write permissions.
6. **Model server configured but not running**: If you've configured a model server (like SGLang, Ollama, etc.) but it's not starting correctly:
   - Verify the server process is actually running (`ps aux | grep <server_name>`).
   - Check that the port mentioned in the configuration is available (`netstat -tuln | grep <port>`).
   - Test connectivity to the server using curl or similar (`curl http://localhost:<port>`).
   - Confirm the environment variables are set correctly, particularly for binary paths and virtual environments.

If you encounter any other issues, refer to the project documentation or contact the maintainers for support.

## Verification

Verify that the application is running correctly:

```bash
curl -s http://localhost:9130/api/health
```

This should return: `{"status":"healthy"}`