#!/usr/bin/env python3
"""Harness resolution and launch-command building for DPMtF roles.

The preferred_cloud_harness flow treats *role*, *model*, *harness* and
*execution lifecycle* as related but separable concerns. This module is the
DPMtF-side seam: it preserves the historical consumer surface tested by the
flow regression suite (``resolve_harness``, ``is_native``, ``missing_env``,
``describe_missing``, ``build_launch_command``, ``build_dsh_invocation``,
``build_task_invocation``) while delegating the actual harness identity and
command-shape logic to the standalone ``harness_allocator`` companion
package located via ``config.get_project_path`` (or the ``HARNESS_ALLOCATOR_PATH`` env var).

Delegation boundary (this module never duplicates what the standalone already
owns):

- ``resolve_harness`` — *identity*, with a DPMtF-only fallback to
  ``"opencode"`` so existing role rows without ``default_harness_source`` keep
  working. No silent harness substitution beyond that explicit fallback.
- ``is_native`` / ``missing_env`` / ``describe_missing`` — thin delegates.
- ``build_launch_command`` / ``build_dsh_invocation`` / ``build_task_invocation`` —
  call the standalone's argv builders and re-render to a shell-quoted
  string. The argv-list form is what the standalone's ``execute`` consumes
  for the actual ``subprocess.Popen``; this module continues to expose the
  historical shell-string form so ``harness_terminal.execute`` and any other
  consumer keeps working byte-for-byte.

The model identity still lives in ``bridge_roles.default_model_alias`` (DPMtF
resolves the model first via Model Allocator); this module only renders the
already-resolved alias into the harness's native CLI. No ``resolve_model()``
responsibility, no silent model/harness substitution.

The standalone package is located through ``config.get_project_path`` (or
the ``HARNESS_ALLOCATOR_PATH`` environment variable for tests), never a
hardcoded path. ``config.py`` is out of scope and is never edited here.
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402

#: Harnesses DPMtF launches directly (the model allocator has no client for them).
#: Re-exported for tests that assert against the historical public attribute.
NATIVE_HARNESSES = ("dsh", "codex")

#: env var -> human description, for a safe, useful error when a credential is missing.
#: Re-exported: delegate answers come from the standalone, but the surface stays.
REQUIRED_ENV = {
    "dsh": {"DEEPSEEK_API_KEY": "DeepSeek Harness direct DeepSeek API"},
    "codex": {"MINIMAX_API_KEY": "Codex MiniMax M3 provider"},
}


def _standalone():
    """The approved standalone ``harness_allocator`` package, lazily imported.

    Located via ``HARNESS_ALLOCATOR_PATH`` (env var override) or
    ``config.get_project_path('harness-allocator')``. Never a hardcoded
    path. Cached on the module so the import cost is paid once.
    """
    cached = getattr(_standalone, "_cache", None)
    if cached is not None:
        return cached
    env_path = os.environ.get("HARNESS_ALLOCATOR_PATH")
    pkg_dir = env_path or config.get_project_path("harness-allocator")
    pkg_parent = str(Path(pkg_dir).resolve())
    if pkg_parent not in sys.path:
        sys.path.insert(0, pkg_parent)
    import harness_allocator as ha  # noqa: E402 — late import by design
    _standalone._cache = ha
    return ha


def resolve_harness(role_config):
    """The harness key for a role, falling back to opencode when no source is set.

    ``role_config`` is a mapping of bridge_roles columns (the same shape
    ``load_role_from_db`` returns). The delegation to the standalone returns
    the empty string when the role carries no harness key; we apply the
    DPMtF-only explicit fallback to ``"opencode"`` here so existing rows
    without ``default_harness_source`` keep routing through the default harness
    (no silent harness substitution beyond that one explicit default).
    """
    ha = _standalone()
    role_dict = role_config if isinstance(role_config, dict) else {}
    harness_key = ha.resolve_harness(role_dict)
    return harness_key or "opencode"


def is_native(harness):
    """True when DPMtF builds the launch command itself for this harness."""
    return _standalone().is_native(harness)


def missing_env(harness):
    """Environment variable names required by a native harness that are unset.

    Returns a list (possibly empty). A non-native harness returns an empty list.
    """
    return _standalone().missing_env(harness)


def describe_missing(harness, missing):
    """A one-line, human-safe error naming what is missing (never the value)."""
    return _standalone().describe_missing(harness, missing)


def get_codex_fresh_context_policy() -> str:
    """The optional Codex fresh-context policy from the standalone allocator."""
    return _standalone().get_codex_fresh_context_policy()


def _model_target_from_role(role_config):
    """Extract the already-resolved model target from a role mapping.

    Pure passthrough: returns the empty string when the role carries no
    model. The standalone package never resolves a model from the role —
    it only ever reads what DPMtF already resolved upstream.
    """
    if not isinstance(role_config, dict):
        return ""
    return (role_config.get("default_model_alias") or "").strip()


def build_launch_command(harness, role_config, cfg=None, task=None):
    """The shell command that starts a native harness.

    - ``codex`` returns the resident TUI command (``codex -m <model>``).
    - ``dsh`` returns the one-shot headless invocation (``dsh --profile
      headless --patch <patch> [task]``).

    Returns a single shell string. Raises ValueError for a non-native harness.
    ``cfg`` defaults to this project's config module and is injectable for
    tests. The implementation delegates to the standalone ``build_launch_argv``
    and renders the resulting argv as a shell-quoted string.
    """
    if cfg is None:
        cfg = config
    if harness == "codex":
        return _codex_command(role_config, cfg)
    if harness == "dsh":
        return build_dsh_invocation(role_config, task, cfg)
    # Every other native harness (qwen, goose, aider, crush, sweagent) is
    # built by the standalone against ITS OWN config, deliberately — and the
    # omission of ``cfg`` below is the whole point, not an oversight.
    #
    # codex and dsh read their knobs from DPMtF's config.py because they
    # predate harness-allocator. The launch knobs of a harness DPMtF never
    # modelled belong to the component that owns interface launches, and
    # mirroring six getters into config.py would create two surfaces for one
    # setting whose defaults could silently drift apart. So DPMtF asks for
    # the argv and does not attempt to configure it.
    ha = _standalone()
    if not ha.is_native(harness):
        raise ValueError(f"not a native harness: {harness!r}")
    argv = ha.build_launch_argv(
        harness,
        model_target=_model_target_from_role(role_config),
        task=task,
    )
    return " ".join(shlex.quote(part) for part in argv)


class _ResolvedEndpoint:
    """The standalone's config with its endpoint replaced by a resolved one.

    A native harness reaches its model over an OpenAI-compatible endpoint
    that only the MODEL allocator knows: the port a runtime profile got, and
    the real model name behind an alias. harness-allocator's env builders
    read that endpoint from their own config, which is empty by default —
    empty means "the harness's own default endpoint", which for Qwen Code is
    a cloud service, not the local server the role was allocated.

    That failure is silent and expensive: the role launches, answers, and
    bills, against the wrong model. So the endpoint is injected rather than
    configured, and everything else still comes from the standalone — the
    ``/v1`` forcing and the read-the-key-by-name indirection stay in the one
    place that owns them.
    """

    def __init__(self, base, base_url):
        self._base = base
        self._base_url = base_url

    def __getattr__(self, name):
        return getattr(self._base, name)

    def get_qwen_base_url(self):
        return self._base_url


def build_native_child_env(harness, model_target, base_url):
    """Endpoint environment overrides for a native harness, or ``{}``.

    ``base_url`` is the resolved endpoint from the model allocator (scheme,
    host and port); the standalone appends ``/v1`` when it is missing. A
    harness the standalone has no env builder for returns an empty dict,
    which means "inherit the parent environment" — never a guess.
    """
    ha = _standalone()
    from harness_allocator import adapter as ha_adapter  # noqa: E402

    builder = getattr(ha_adapter, f"build_{harness}_env", None)
    if builder is None:
        return {}
    cfg = _ResolvedEndpoint(ha.config, base_url) if base_url else ha.config
    env = builder(model_target=model_target, cfg=cfg)

    # A locally allocated runtime needs no credential, but an OpenAI-compatible
    # CLIENT generally refuses to consider a provider configured without one.
    # Qwen Code drops into its interactive "Connect a Provider" wizard when
    # OPENAI_API_KEY is unset, however correct the endpoint is — and a role
    # sitting in a wizard swallows every dispatch it is sent.
    #
    # This is a protocol filler, not a secret, and it is deliberately NOT
    # configuration: harness-allocator stores the NAME of a variable holding a
    # real key, and writing a fake value into that slot would corrupt an
    # indirection that exists to keep secrets out of config files. DPMtF is
    # also the only layer that knows the endpoint is loopback, which is what
    # makes the filler safe.
    #
    # Narrow on purpose: only a loopback endpoint, and only when no real key
    # was wired. A remote endpoint or a configured key is left exactly alone,
    # so this can never mask a genuine missing credential.
    if _is_loopback(base_url) and "OPENAI_API_KEY" not in env:
        env["OPENAI_API_KEY"] = "local-no-auth-required"
    return env


def _is_loopback(base_url):
    """True when a URL points at this machine, so no credential can be needed."""
    if not base_url:
        return False
    try:
        host = urlparse(base_url).hostname or ""
    except ValueError:
        return False
    return host in ("127.0.0.1", "::1", "localhost")


def build_dsh_invocation(role_config, task=None, cfg=None):
    """The one-shot DeepSeek Harness invocation: `dsh --profile <profile>
    --patch <patch> [task]`.

    ``task`` is the supervisor turn's prompt/context. When it is supplied it
    is appended as the final argv element; when it is omitted the command
    still resolves (for dry-run resolution and command-surface tests) with
    the profile and patch intact. The profile is whatever
    ``cfg.get_dsh_profile()`` resolves — ``headless`` by default, per the
    verified execution path.

    Implementation: delegates to the standalone ``build_dsh_argv`` and joins
    the resulting argv as a shell-quoted string, so the DPMtF-side string
    surface and the standalone's argv surface never diverge.
    """
    if cfg is None:
        cfg = config
    ha = _standalone()
    argv = ha.build_dsh_argv(
        model_target=_model_target_from_role(role_config),
        task=task,
        cfg=cfg,
    )
    return " ".join(shlex.quote(part) for part in argv)


def build_task_invocation(harness, role_config, task, cfg=None):
    """Build the shell command that executes ``task`` through ``harness``.

    The harness-neutral entry point the Harness Terminal uses: for one-shot
    harnesses it returns the single command that runs ``task``; resident TUIs
    (codex, claude-code, opencode) have no one-shot form and raise, because
    they are driven interactively rather than through the terminal.
    Delegates to the standalone ``build_task_argv`` and re-renders to a
    shell-quoted string.
    """
    if cfg is None:
        cfg = config
    ha = _standalone()
    argv = ha.build_task_argv(
        harness,
        model_target=_model_target_from_role(role_config),
        task=task,
        cfg=cfg,
    )
    return " ".join(shlex.quote(part) for part in argv)


def _profile_from_role(role_config):
    """The resolved ``harness_profile`` for a role (or ``""`` when absent).

    The role mapping may carry the key as ``harness_profile`` (D2b's
    ``get_flow_roles`` shape) or as ``default_harness_profile`` (the
    ``load_role_from_db`` shape used by ``relaunch_in_session``). Both
    forms are accepted here so callers do not have to normalise.
    Strips whitespace and returns the empty string on any falsy value —
    the empty string is the "today's behaviour" sentinel for the
    standalone adapter.
    """
    if not isinstance(role_config, dict):
        return ""
    raw = role_config.get("harness_profile")
    if raw is None or raw == "":
        raw = role_config.get("default_harness_profile")
    return (raw or "").strip()


def _apply_codex_profile_env(profile):
    """Export ``CODEX_PROFILE`` when ``profile`` is non-empty; pop it when empty.

    The D1 adapter (harness-allocator) reads the profile through its
    config module, which checks ``CODEX_PROFILE`` from the env first.
    Setting it here makes DPMtF's launch path observable to the adapter
    without DPMtF ever editing its own config.py.

    The contract is asymmetric: a non-empty profile is exported (and
    left set — the role is mid-launch, the env should reflect the
    resolved profile); an empty / absent profile is UNSET (the env var
    MUST NOT carry over from a previous launch — that would silently
    activate a stale profile on a profile-less role).

    Returns the profile string for caller convenience.
    """
    if profile:
        os.environ["CODEX_PROFILE"] = profile
    else:
        os.environ.pop("CODEX_PROFILE", None)
    return profile


class _ProfileAwareCfg:
    """Wraps a DPMtF config with the profile getters the D1 adapter reads.

    Run 024 / D2: the standalone adapter's ``_codex_argv`` reads the
    profile via ``getattr(cfg, "get_codex_profile", lambda: "")()``.
    DPMtF's ``config`` module has no ``get_codex_profile``; left bare,
    the adapter's ``getattr`` falls through to the empty-string lambda
    and the profile is silently ignored.

    This wrapper forwards every other attribute to the wrapped config
    (so today's add-dirs, sandbox, workdir, etc. all keep resolving
    from the real DPMtF values), and exposes the three profile getters
    the adapter calls. The profile getters read from the env, NOT from
    the DPMtF config — the contract is "DPMtF exports CODEX_PROFILE,
    the adapter reads it"; the values live where D2 set them, not
    where some other module might shadow them.

    The gpu sandbox / add-dirs getters carry the DPMtF-side defaults
    (``danger-full-access`` / ``[]``) when no override env is set.
    config.py is OUT OF SCOPE and is never edited here — defaults are
    inlined below because the run-024 §3 fence forbids touching
    config.py.
    """
    def __init__(self, base_cfg):
        # __getattr__ runs only on MISSING attributes, so the attributes
        # we set explicitly below take precedence. Setting them to
        # None here is fine — __getattr__ will not be consulted.
        object.__setattr__(self, "_base", base_cfg)

    def __getattr__(self, name):
        # Forward every other attribute to the real DPMtF config.
        return getattr(self._base, name)

    def get_codex_profile(self):
        """Env ``CODEX_PROFILE`` (set by D2 right before this call).

        Strips whitespace and returns ``""`` when absent — the
        standalone adapter treats empty profile as "today's behaviour".
        """
        env = os.environ.get("CODEX_PROFILE")
        if env is None:
            return ""
        return env.strip()

    def get_codex_profile_gpu_sandbox(self):
        """Override channel for the gpu sandbox mode (DPMtF default: ``danger-full-access``).

        Reads ``CODEX_PROFILE_GPU_SANDBOX`` from the env when set, else
        returns the DPMtF-side default. config.py is out of scope, so
        the default is inlined.
        """
        env = os.environ.get("CODEX_PROFILE_GPU_SANDBOX")
        if env is not None and env.strip():
            return env.strip()
        return "danger-full-access"

    def get_codex_profile_gpu_add_dirs(self):
        """Override channel for the gpu add-dirs (DPMtF default: ``[]``).

        Reads ``CODEX_PROFILE_GPU_ADD_DIRS`` from the env when set
        (colon- or comma-separated), else returns the DPMtF-side
        default of an empty list. config.py is out of scope, so the
        default is inlined.
        """
        raw = os.environ.get("CODEX_PROFILE_GPU_ADD_DIRS")
        if raw is None or not raw.strip():
            return []
        return [p.strip() for p in raw.replace(",", ":").split(":") if p.strip()]


def _codex_command(role_config, cfg):
    """`codex -m <model>` — model selected explicitly, provider from user config.

    Codex's MiniMax M3 provider is configured at the user level (its catalog),
    which the flow deliberately does not duplicate. Passing the model here is
    selection, not configuration — the same way a Claude Code role names its
    alias.

    Implementation: delegates to the standalone ``build_launch_argv('codex', ...)``
    so the argv shape and the shell-quoted string stay in sync.

    Run 024 / D2: the resolved ``harness_profile`` from ``role_config`` is
    exported as ``CODEX_PROFILE`` in the launch environment BEFORE the
    adapter renders the argv. NULL / empty profile unsets the env var, so
    today's launch is byte-identical. The adapter sees the profile
    through a ``_ProfileAwareCfg`` wrapper around the DPMtF config so the
    profile getters resolve from the env without editing config.py.
    """
    profile = _profile_from_role(role_config)
    _apply_codex_profile_env(profile)
    ha = _standalone()
    # ALWAYS wrap so the adapter's ``getattr(cfg, "get_codex_profile")``
    # call returns the env-driven value rather than falling through to
    # the empty-string lambda. When profile is empty the wrapper still
    # reads "" from the env (the env is unset) and the profile-less
    # argv path is byte-identical to today.
    effective_cfg = _ProfileAwareCfg(cfg if cfg is not None else config)
    argv = ha.build_launch_argv(
        "codex",
        model_target=_model_target_from_role(role_config),
        cfg=effective_cfg,
    )
    return " ".join(shlex.quote(part) for part in argv)


def launch_spec(role_config):
    """The allocator's LaunchSpec dict for the role's resolved harness.

    Thin delegate: resolve the harness via the existing
    :func:`resolve_harness` (which applies the opencode fallback for
    harness-less role configs), then return the standalone's
    ``get_launch_spec``. ``resolve_harness`` already applies the DPMtF-only
    explicit fallback so existing rows without ``default_harness_source``
    keep routing through the default harness — this delegate does NOT
    duplicate that logic.

    Raises ``UnknownHarnessError`` (re-exported from the standalone via the
    import surface) if the resolved harness is not registered with the
    allocator. The error message names the unknown harness.
    """
    _standalone()  # ensure the package parent dir is on sys.path
    import harness_allocator.launchspec as halaunchspec  # noqa: E402
    harness_key = resolve_harness(role_config)
    return halaunchspec.get_launch_spec(harness_key)


def launchspec_disagreements():
    """Compare each LaunchSpec + StopSpec field against DPMtF's live behaviour.

    Returns a list of disagreement descriptor strings; an empty list means
    full agreement. The roster is DERIVED from the allocator's
    ``SUPPORTED_HARNESSES + EXPERIMENTAL_HARNESSES`` (imported from
    :mod:`harness_allocator.capabilities`) — never hand-listed.

    The compared field set is the SET DPMtF STILL derives independently.
    After Run 041 D1–D3, several LaunchSpec / StopSpec fields are CONSUMED
    by DPMtF (not transcribed): start_coding reads mode / needs_initial_prompt
    / anchor from the spec (D1); runtime_owner reads the resident-StopSpec
    signals / grace_seconds / verify from the spec (D2); chain_watchdog
    derives ACTIVITY_MARKERS from every harness's declared activity_markers
    (D3). For an honest oracle, those fields' "today" side MUST NOT be
    rebuilt from ``get_launch_spec`` / ``get_stop_spec`` output — the
    oracle would then agree with itself vacuously and could never
    disagree. GOAL.md §2's honesty rule binds this: every consumed
    field is RETIRED from the compared set, and its frozen literal of
    TODAY's value lives in ``tests/test_launchspec_literals.py`` (D4).
    A future spec edit that changes a retired field turns the frozen
    literal test RED — the regression guard replaces the disagreement
    path the oracle used to provide.

    Fields STILL compared (every compared field's "today" side is
    built from a non-spec source, satisfying GOAL.md §2's honesty rule):

      - LaunchSpec:
          * ``required_env`` (set of names) — from
            ``hdef.REQUIRED_ENV.get(harness, {}).keys()`` plus
            ``adapter.build_sweagent_env()`` for sweagent.
          * ``launch_owner`` — ``"harness_allocator"`` iff
            ``hdef.is_native(harness)`` else ``"model_allocator"``.
      - StopSpec (terminal_wrapped + one_shot harnesses only —
        the resident stop fields are RETIRED, since runtime_owner's
        D2 spec-driven ``_kill_by_spec`` reads them from the spec):
          * ``signals`` — ``["SIGINT","SIGTERM","SIGKILL"]``.
          * ``grace_seconds`` — ``int(hinvoke.CANCEL_GRACE_SECONDS)``.
          * ``verify`` — ``"pid_gone"``.

    The resident-vs-terminal/one-shot classification is a TRANSCRIBED
    branch on harness names (the pre-D1 start_coding form); it is used
    to decide which stop fields are independently derivable today,
    NOT to derive any consumed LaunchSpec/StopSpec value. Resident
    harnesses simply carry no "stop" key on the today dict, and the
    stop-field loop is guarded so retired fields are not compared.

    Each disagreement is a string of the form
    ``"<harness>.<field>: spec=<repr(spec_value)> dpmf=<repr(today_value)>"``.
    The iteration order is fixed: harnesses in derived-roster order,
    then fields in a fixed order, so the output is deterministic for
    diff-friendly output.

    Required-script-path setup: this module sits at
    ``scripts/bridgeV002/harness.py``. The DPMtF-side sources
    (``chain_watchdog``, ``runtime_owner``) live in the same directory
    and need that directory on ``sys.path`` to import as bare names. The
    standalone allocator submodules (``harness_allocator.capabilities``
    etc.) are accessible through the package import established by
    :func:`_standalone`.
    """
    # Lazy-add scripts/bridgeV002 to sys.path (idempotent). This module
    # sits at scripts/bridgeV002/harness.py, but the parent directory is
    # what DPMtF's parent-directory math put on sys.path — this directory
    # is a separate concern.
    _scripts_dir = str(Path(__file__).resolve().parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)

    # _standalone() adds the harness-allocator parent dir to sys.path so
    # ``import harness_allocator`` works. Call it FIRST so the
    # ``harness_allocator.capabilities`` etc. submodule imports below
    # resolve.
    _standalone()

    # Late imports — see "Required-script-path setup" in the docstring.
    import harness_allocator.capabilities as hcaps  # noqa: E402 — late import by design
    import harness_allocator.invoke as hinvoke  # noqa: E402
    import harness_allocator.definition as hdef  # noqa: E402
    import harness_allocator.adapter as hadapter  # noqa: E402
    import harness_allocator.launchspec as halaunchspec  # noqa: E402
    import chain_watchdog  # noqa: E402 — DPMtF-side
    import runtime_owner  # noqa: E402 — DPMtF-side

    # Build the "today" side independently of the spec.
    today_by_harness = {
        h: _today_behavior(h, hdef, hadapter, hinvoke, chain_watchdog, runtime_owner)
        for h in tuple(hcaps.SUPPORTED_HARNESSES) + tuple(hcaps.EXPERIMENTAL_HARNESSES)
    }

    disagreements = []

    # Fixed field order for deterministic output (handoff §STEP 2):
    #   LaunchSpec (compared): required_env, launch_owner
    #     [RETIRED: mode, needs_initial_prompt, anchor — consumed by start_coding (D1);
    #                activity_markers — consumed by chain_watchdog (D3).]
    #   StopSpec (compared for terminal_wrapped + one_shot harnesses):
    #     signals, grace_seconds, verify.
    #     [RETIRED for resident_tui harnesses (codex, claude-code, opencode):
    #                consumed by runtime_owner._kill_by_spec (D2).]
    launch_field_order = (
        "required_env",
        "launch_owner",
    )
    stop_field_order = (
        "signals",
        "grace_seconds",
        "verify",
    )

    for harness in tuple(hcaps.SUPPORTED_HARNESSES) + tuple(hcaps.EXPERIMENTAL_HARNESSES):
        spec_launch = halaunchspec.get_launch_spec(harness)
        spec_stop = halaunchspec.get_stop_spec(harness)
        today = today_by_harness[harness]

        for field in launch_field_order:
            spec_value = spec_launch[field]
            today_value = today["launch"][field]
            if field == "required_env":
                # Compare as SET equality — order is not contractually bound.
                if set(spec_value) != set(today_value):
                    disagreements.append(
                        f"{harness}.{field}: spec={sorted(spec_value)!r} dpmf={sorted(today_value)!r}"
                    )
            else:
                if spec_value != today_value:
                    disagreements.append(
                        f"{harness}.{field}: spec={spec_value!r} dpmf={today_value!r}"
                    )

        # Resident harnesses carry no "stop" key (retired; frozen literal
        # in tests/test_launchspec_literals.py). The loop below compares
        # stop fields ONLY when the today dict still derives them
        # independently (terminal_wrapped + one_shot — invoke.py's cancel
        # ladder, OUT of scope).
        if "stop" in today:
            for field in stop_field_order:
                spec_value = spec_stop[field]
                today_value = today["stop"][field]
                if spec_value != today_value:
                    disagreements.append(
                        f"{harness}.{field}: spec={spec_value!r} dpmf={today_value!r}"
                    )

    return disagreements


def _today_behavior(harness, hdef, hadapter, hinvoke, chain_watchdog, runtime_owner):
    """DPMtF + allocator "today's behaviour" for ``harness`` -- independent of spec.

    The "today" side is built from constants IMPORTED from DPMtF/allocator
    source (no literals) and from a single TRANSCRIBED BRANCH on harness
    names. NEVER read from ``get_launch_spec`` / ``get_stop_spec`` --
    any field whose today-side was the spec would make the oracle
    vacuously agree with itself (GOAL.md §2).

    Compared today-derivable fields (this run still derives):

      - LaunchSpec:
          * ``required_env`` (set of names) -- from
            ``hdef.REQUIRED_ENV.get(harness, {}).keys()`` plus
            ``adapter.build_sweagent_env()`` for sweagent.
          * ``launch_owner`` -- ``"harness_allocator"`` iff
            ``hdef.is_native(harness)`` else ``"model_allocator"``.
      - StopSpec (terminal_wrapped + one_shot harnesses only):
          * ``signals`` -- ``["SIGINT","SIGTERM","SIGKILL"]``.
          * ``grace_seconds`` -- ``int(hinvoke.CANCEL_GRACE_SECONDS)``.
          * ``verify`` -- ``"pid_gone"``.

    Resident-vs-terminal/one-shot classification (transcribed branch):

      codex, claude-code, opencode -> resident_tui (the pre-D1
          start_coding form); dsh, qwen, goose, crush, sweagent, aider
          -> terminal_wrapped or one_shot. The branch is used ONLY to
          decide whether the today dict carries a "stop" key (resident
          stop fields are retired -- their frozen literal lives in
          ``tests/test_launchspec_literals.py``).

    RETIRED compared fields (no longer carried on the today dict):

      - Launch ``mode``, ``needs_initial_prompt``, ``anchor`` -- read by
        ``start_coding._launch_decisions_for`` (Run 041 D1).
      - Launch ``activity_markers`` -- derived by
        ``chain_watchdog._derive_activity_markers`` (Run 041 D3).
      - Stop resident-TUI fields (``signals``, ``grace_seconds``,
        ``verify`` for codex / claude-code / opencode) -- read by
        ``runtime_owner.stop_spec_for`` via ``harness_allocator.launchspec.
        get_stop_spec`` then applied by ``runtime_owner._kill_by_spec``
        (Run 041 D2). ``_default_kill`` is the pre-D2 path; the spec-driven
        ``_kill_by_spec`` is the post-D2 path, so a "today" value
        transcribed from ``_default_kill`` would describe DEAD behaviour.

    Returns a dict with ``"launch"`` (2 keys: required_env, launch_owner)
    and OPTIONALLY ``"stop"`` (3 keys: signals, grace_seconds, verify) for
    terminal_wrapped + one_shot harnesses only. Resident harnesses return
    only ``"launch"``; the disagreement loop above guards on
    ``"stop" in today`` to skip retired stop fields.
    """
    # Resident vs terminal/one-shot -- a TRANSCRIBED branch on harness
    # names (the pre-D1 start_coding form), NOT read from the spec.
    # mode itself is RETIRED, but the split is still needed to decide
    # which STOP fields are independently derivable.
    is_resident = harness in ("codex", "claude-code", "opencode")

    # required_env -- STAYS (independent: definition.REQUIRED_ENV + sweagent builder).
    env_names = set(hdef.REQUIRED_ENV.get(harness, {}).keys())
    if harness == "sweagent":
        # The three SWE_AGENT_*_DIR names are LOAD-BEARING for the bare CLI
        # (CONFIG_DIR.is_dir() assertion); derive them from the builder's
        # return value rather than copy as a literal.
        sweagent_env = hadapter.build_sweagent_env()
        env_names.update(sweagent_env.keys())

    launch_owner = "harness_allocator" if hdef.is_native(harness) else "model_allocator"

    result = {
        "launch": {
            "required_env": sorted(env_names),
            "launch_owner": launch_owner,
        },
    }

    if not is_resident:
        # terminal_wrapped + one_shot: invoke.py's cancel ladder is the
        # still-independent source (out of scope, unchanged).
        result["stop"] = {
            "signals": ["SIGINT", "SIGTERM", "SIGKILL"],
            "grace_seconds": int(hinvoke.CANCEL_GRACE_SECONDS),
            "verify": "pid_gone",
        }
    # resident: NO "stop" key -> the disagreement loop below skips it
    # (retired; guarded by tests/test_launchspec_literals.py).

    return result


if __name__ == "__main__":
    print("Harness resolution module — command builder and credential checks only.")
