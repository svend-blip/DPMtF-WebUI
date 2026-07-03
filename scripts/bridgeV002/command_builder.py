"""Machine Profile Fase 2A — Command builder for role start commands.

Translates logical role fields (runtime, provider, model) into concrete
start commands using Machine Profile configuration.

Returns structured command objects — never raw shell strings directly.
Renderer handles tmux-safe shell string conversion.
"""

import os
import shlex
import shutil


def build_start_command(runtime, provider, model, role_key, machine_profile,
                        config_dir=None):
    """Build a start command object from logical role fields + Machine Profile.

    Args:
        runtime: str — which program starts the role (claude, opencode, freebuff)
        provider: str or None — where the model comes from
        model: str — which model to use
        role_key: str — the role's unique key (for config_dir resolution)
        machine_profile: dict — from config.get_machine_profile()
        config_dir: str or None — override config directory name (OpenCode only)

    Returns:
        dict with keys: cwd (str), env (dict), argv (list[str])

    Raises:
        ValueError: if runtime/provider combination is unsupported,
                    if required fields are missing,
                    if required binaries are not found in Machine Profile
    """
    # Validate required fields
    if not runtime:
        raise ValueError(
            f"Role {role_key} has use_machine_profile flow enabled "
            f"but missing default_runtime"
        )
    if not provider and runtime != "freebuff":
        raise ValueError(
            f"Role {role_key} has use_machine_profile flow enabled "
            f"but missing default_provider"
        )
    if not model:
        raise ValueError(
            f"Role {role_key} has use_machine_profile flow enabled "
            f"but missing default_model"
        )

    # Look up builder
    builder_key = (runtime, provider if provider else None)
    builder = SUPPORTED_COMMAND_BUILDERS.get(builder_key)
    if builder is None:
        raise ValueError(
            f"Unsupported runtime/provider combination: {runtime}/{provider}"
        )

    # Resolve config directory: explicit config_dir > role_key
    effective_config_dir = config_dir or role_key

    return builder(runtime, provider, model, effective_config_dir, machine_profile)


# ── Builder registry ──────────────────────────────────────────


SUPPORTED_COMMAND_BUILDERS = {}


def _register(runtime, provider):
    """Decorator to register a builder function."""
    def decorator(func):
        SUPPORTED_COMMAND_BUILDERS[(runtime, provider)] = func
        return func
    return decorator


# ── Helpers ───────────────────────────────────────────────────


def _resolve_binary(binary_ref, binaries, runtime_name):
    """Resolve a binary_ref from Machine Profile binaries section.

    Returns the binary path/name for use in command argv.
    Raises ValueError if binary is not found.
    """
    binary_path = binaries.get(binary_ref, binary_ref)

    if os.path.isabs(binary_path):
        if os.path.isfile(binary_path) and os.access(binary_path, os.X_OK):
            return binary_path
        raise ValueError(f"Runtime binary not found: {binary_path}")

    # Non-absolute — verify it exists on PATH
    if shutil.which(binary_path) is None:
        raise ValueError(f"Runtime binary not found on PATH: {binary_path}")
    return binary_path


def _get_provider_config(provider_key, providers):
    """Get provider config, raising if not found."""
    if provider_key not in providers:
        raise ValueError(
            f"Provider not configured in Machine Profile: {provider_key}"
        )
    return providers[provider_key]


def _get_runtime_config(runtime_key, runtimes):
    """Get runtime config, returning empty dict if not found."""
    return runtimes.get(runtime_key, {})


# ── Individual builders ───────────────────────────────────────


@_register("claude", "local_ollama")
@_register("claude", "cloud_ollama")
def build_claude_ollama_command(runtime, provider, model, role_key, mp):
    """Build Claude + Ollama (local or cloud) command."""
    binaries = mp.get("binaries", {})
    providers = mp.get("providers", {})
    runtimes = mp.get("runtimes", {})
    paths = mp.get("paths", {})

    claude_bin = _resolve_binary("claude", binaries, "claude")
    provider_cfg = _get_provider_config(provider, providers)
    runtime_cfg = _get_runtime_config("claude", runtimes)

    endpoint = provider_cfg.get("endpoint", "http://127.0.0.1:11434")
    auth_token = provider_cfg.get("auth_token", "ollama")

    # Security: only "ollama" token is allowed in command object
    if auth_token != "ollama":
        raise ValueError(
            f"auth_token for provider '{provider}' is not 'ollama' — "
            f"cannot include in command object. Use environment variable instead."
        )

    env = dict(runtime_cfg.get("default_env", {}))
    env.update(provider_cfg.get("env", {}))
    env["ANTHROPIC_BASE_URL"] = endpoint
    env["ANTHROPIC_AUTH_TOKEN"] = auth_token

    return {
        "env": env,
        "argv": [claude_bin, "--model", model],
    }


@_register("claude", "openrouter")
def build_claude_openrouter_command(runtime, provider, model, role_key, mp):
    """Build Claude + OpenRouter command.

    Verifies the API key exists at build time, but passes it as a shell
    variable reference ($OPENROUTER_API_KEY) so the key is never hardcoded
    in the tmux pane output. The shell in the tmux session resolves it.

    Sets ANTHROPIC_API_KEY="" explicitly — otherwise Claude Code may fall
    back to direct Anthropic auth instead of routing through OpenRouter.
    """
    binaries = mp.get("binaries", {})
    providers = mp.get("providers", {})
    runtimes = mp.get("runtimes", {})

    claude_bin = _resolve_binary("claude", binaries, "claude")
    provider_cfg = _get_provider_config(provider, providers)
    runtime_cfg = _get_runtime_config("claude", runtimes)

    endpoint = provider_cfg.get("endpoint", "https://openrouter.ai/api")

    # Verify API key exists at build time, but pass as shell variable
    # reference so the literal key never appears in the tmux pane.
    env_key = provider_cfg.get("env_key", "OPENROUTER_API_KEY")
    if not os.environ.get(env_key):
        raise ValueError(
            f"Environment variable '{env_key}' is not set. "
            f"OpenRouter requires an API key. Set {env_key} in your shell "
            f"before starting the role."
        )

    env = dict(runtime_cfg.get("default_env", {}))
    env.update(provider_cfg.get("env", {}))
    env["ANTHROPIC_BASE_URL"] = endpoint
    env["ANTHROPIC_AUTH_TOKEN"] = f"${env_key}"
    # Must be explicitly empty — otherwise Claude Code may fall back to
    # direct Anthropic auth instead of routing through OpenRouter.
    env["ANTHROPIC_API_KEY"] = ""

    return {
        "env": env,
        "argv": [claude_bin, "--model", model],
    }


@_register("opencode", "local_ollama")
def build_opencode_ollama_command(runtime, provider, model, config_dir, mp):
    """Build OpenCode + local Ollama command."""
    binaries = mp.get("binaries", {})
    providers = mp.get("providers", {})
    runtimes = mp.get("runtimes", {})
    paths = mp.get("paths", {})

    opencode_bin = _resolve_binary("opencode", binaries, "opencode")
    provider_cfg = _get_provider_config(provider, providers)
    runtime_cfg = _get_runtime_config("opencode", runtimes)

    config_base = runtime_cfg.get("config_base", "$HOME/.config/opencode-roles")
    full_config_dir = f"{config_base}/{config_dir}"

    env = dict(runtime_cfg.get("default_env", {}))
    env.update(provider_cfg.get("env", {}))
    env["OPENCODE_CONFIG_DIR"] = full_config_dir
    env["OPENCODE_CONFIG"] = f"{full_config_dir}/opencode.json"

    return {
        "env": env,
        "argv": [opencode_bin, "--model", f"ollama/{model}"],
    }


@_register("opencode", "openrouter")
def build_opencode_openrouter_command(runtime, provider, model, config_dir, mp):
    """Build OpenCode + OpenRouter command.

    OpenRouter API key comes from environment — NOT included in command object.
    """
    binaries = mp.get("binaries", {})
    providers = mp.get("providers", {})
    runtimes = mp.get("runtimes", {})

    opencode_bin = _resolve_binary("opencode", binaries, "opencode")
    provider_cfg = _get_provider_config(provider, providers)
    runtime_cfg = _get_runtime_config("opencode", runtimes)

    config_base = runtime_cfg.get("config_base", "$HOME/.config/opencode-roles")
    full_config_dir = f"{config_base}/{config_dir}"

    env = dict(runtime_cfg.get("default_env", {}))
    env.update(provider_cfg.get("env", {}))
    env["OPENCODE_CONFIG_DIR"] = full_config_dir
    env["OPENCODE_CONFIG"] = f"{full_config_dir}/opencode.json"

    return {
        "env": env,
        "argv": [opencode_bin, "--model", f"openrouter/{model}"],
    }


@_register("opencode", "opencode_builtin")
def build_opencode_builtin_command(runtime, provider, model, config_dir, mp):
    """Build OpenCode + built-in provider command (no model prefix).

    Used when OpenCode handles the provider directly (e.g. minimax, anthropic).
    Model is passed as-is without openrouter:/ollama: prefix.
    """
    binaries = mp.get("binaries", {})
    providers = mp.get("providers", {})
    runtimes = mp.get("runtimes", {})

    opencode_bin = _resolve_binary("opencode", binaries, "opencode")
    provider_cfg = _get_provider_config(provider, providers)
    runtime_cfg = _get_runtime_config("opencode", runtimes)

    config_base = runtime_cfg.get("config_base", "$HOME/.config/opencode-roles")
    full_config_dir = f"{config_base}/{config_dir}"

    env = dict(runtime_cfg.get("default_env", {}))
    env.update(provider_cfg.get("env", {}))
    env["OPENCODE_CONFIG_DIR"] = full_config_dir
    env["OPENCODE_CONFIG"] = f"{full_config_dir}/opencode.json"

    return {
        "env": env,
        "argv": [opencode_bin, "--model", model],
    }


@_register("freebuff", None)
def build_freebuff_command(runtime, provider, model, role_key, mp):
    """Build Freebuff command. Freebuff is a runtime, not a provider."""
    binaries = mp.get("binaries", {})

    freebuff_bin = _resolve_binary("freebuff", binaries, "freebuff")

    return {
        "env": {},
        "argv": [freebuff_bin],
    }


# ── Renderer ──────────────────────────────────────────────────


def render_tmux_shell_string(command_object):
    """Render a command object to a tmux-safe shell string.

    Builds: ENV=value ENV2=value2 binary --arg

    The caller is responsible for prepending 'cd <dir> && ' if needed.
    Environment variables are set BEFORE the command in the same shell
    invocation — not chained with && between each env var.

    Uses shlex.quote() for safe shell quoting.
    Never uses shell=True internally.

    Args:
        command_object: dict with env, argv

    Returns:
        str — shell command string safe for tmux send-keys

    Raises:
        ValueError: if argv is empty
    """
    env = command_object.get("env", {})
    argv = command_object.get("argv", [])

    if not argv:
        raise ValueError("Command object missing argv")

    env_parts = []
    for key, value in env.items():
        val_str = str(value)
        # Values containing $ are shell variables — use double quotes to allow expansion
        if "$" in val_str:
            env_parts.append(f'{key}="{val_str}"')
        else:
            env_parts.append(f"{key}={shlex.quote(val_str)}")

    argv_part = " ".join(shlex.quote(str(arg)) for arg in argv)

    if env_parts:
        return " ".join(env_parts + [argv_part])

    return argv_part
