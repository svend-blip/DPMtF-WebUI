"""Machine Profile Fase 2A — Command builder for role start commands.

Translates logical role fields (runtime, provider, model) into concrete
start commands using Machine Profile configuration.

Returns structured command objects — never raw shell strings directly.
Renderer handles tmux-safe shell string conversion.
"""

import os
import shlex
import shutil


def build_start_command(runtime, provider, model, role_key, machine_profile):
    """Build a start command object from logical role fields + Machine Profile.

    Args:
        runtime: str — which program starts the role (claude, opencode, freebuff)
        provider: str or None — where the model comes from
        model: str — which model to use
        role_key: str — the role's unique key (for config_dir resolution)
        machine_profile: dict — from config.get_machine_profile()

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

    return builder(runtime, provider, model, role_key, machine_profile)


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
    env["ANTHROPIC_BASE_URL"] = endpoint
    env["ANTHROPIC_AUTH_TOKEN"] = auth_token

    cwd = paths.get("project_root", os.getcwd())

    return {
        "cwd": cwd,
        "env": env,
        "argv": [claude_bin, "--model", model],
    }


@_register("opencode", "local_ollama")
def build_opencode_ollama_command(runtime, provider, model, role_key, mp):
    """Build OpenCode + local Ollama command."""
    binaries = mp.get("binaries", {})
    runtimes = mp.get("runtimes", {})
    paths = mp.get("paths", {})

    opencode_bin = _resolve_binary("opencode", binaries, "opencode")
    runtime_cfg = _get_runtime_config("opencode", runtimes)

    config_base = runtime_cfg.get("config_base", "$HOME/.config/opencode-roles")
    config_dir = f"{config_base}/{role_key}"

    cwd = paths.get("project_root", os.getcwd())

    return {
        "cwd": cwd,
        "env": {
            "OPENCODE_CONFIG_DIR": config_dir,
            "OPENCODE_CONFIG": f"{config_dir}/opencode.json",
        },
        "argv": [opencode_bin, "--model", f"ollama/{model}"],
    }


@_register("opencode", "openrouter")
def build_opencode_openrouter_command(runtime, provider, model, role_key, mp):
    """Build OpenCode + OpenRouter command.

    OpenRouter API key comes from environment — NOT included in command object.
    """
    binaries = mp.get("binaries", {})
    runtimes = mp.get("runtimes", {})
    paths = mp.get("paths", {})

    opencode_bin = _resolve_binary("opencode", binaries, "opencode")
    runtime_cfg = _get_runtime_config("opencode", runtimes)

    config_base = runtime_cfg.get("config_base", "$HOME/.config/opencode-roles")
    config_dir = f"{config_base}/{role_key}"

    cwd = paths.get("project_root", os.getcwd())

    return {
        "cwd": cwd,
        "env": {
            "OPENCODE_CONFIG_DIR": config_dir,
            "OPENCODE_CONFIG": f"{config_dir}/opencode.json",
        },
        "argv": [opencode_bin, "--model", f"openrouter/{model}"],
    }


@_register("freebuff", None)
def build_freebuff_command(runtime, provider, model, role_key, mp):
    """Build Freebuff command. Freebuff is a runtime, not a provider."""
    binaries = mp.get("binaries", {})
    paths = mp.get("paths", {})

    freebuff_bin = _resolve_binary("freebuff", binaries, "freebuff")
    cwd = paths.get("project_root", os.getcwd())

    return {
        "cwd": cwd,
        "env": {},
        "argv": [freebuff_bin],
    }


# ── Renderer ──────────────────────────────────────────────────


def render_tmux_shell_string(command_object):
    """Render a command object to a tmux-safe shell string.

    Builds: cd <cwd> && ENV=value ENV2=value2 binary --arg

    Environment variables are set BEFORE the command in the same shell
    invocation — not chained with && between each env var.

    Uses shlex.quote() for safe shell quoting.
    Never uses shell=True internally.

    Args:
        command_object: dict with cwd, env, argv

    Returns:
        str — shell command string safe for tmux send-keys

    Raises:
        ValueError: if argv is empty
    """
    cwd = command_object.get("cwd", "")
    env = command_object.get("env", {})
    argv = command_object.get("argv", [])

    if not argv:
        raise ValueError("Command object missing argv")

    prefix = ""
    if cwd:
        prefix = f"cd {shlex.quote(cwd)} && "

    env_parts = [
        f"{key}={shlex.quote(str(value))}"
        for key, value in env.items()
    ]

    argv_part = " ".join(shlex.quote(str(arg)) for arg in argv)

    if env_parts:
        return prefix + " ".join(env_parts + [argv_part])

    return prefix + argv_part
