# 101 — CODE FRONTENDS AND PER-FLOW COLD START

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines the rule that makes a flow's **code frontend** a swappable choice
rather than a structural commitment: every flow owns exactly one cold-start
skill, and that skill must work under any supported frontend.

Three frontends are supported. Which one a role uses is a Human decision
recorded in `bridge_roles.allocator_client`, and changing it must never
require rewriting the flow's procedures.

| Frontend | `allocator_client` | Reaches a model through |
|---|---|---|
| Claude Code | `claude-code` | Anthropic-shaped endpoint |
| OpenCode | `opencode` | `@ai-sdk/openai-compatible` provider block |
| Pi | `pi` | built-in provider, or a custom one in `models.json` |

## When to Use

- **Human:** before swapping a role's frontend, or adding a flow.
- **Architect / Supervisor:** when writing or revising a flow's cold-start.
- **Review:** when a flow's procedures are changed.

---

## The Rule

**One cold-start skill per flow. Not one per frontend.**

The obvious reading of "it must work in all three" is three copies. That is
wrong, and measurably so: a single `SKILL.md` placed in the home-global skill
locations is discovered by all three frontends today. Three copies would be
three files that drift, and the drift would surface as a role behaving
differently after a frontend swap — the exact failure this rule exists to
prevent.

## Placement Is Load-Bearing

A worker runs with its working directory set to the **target project**, not
to Father. A skill that lives only in this repository is therefore invisible
to precisely the sessions that need it. Measured 2026-08-12: `opencode debug
skill` run from a target project lists none of the flow skills stored in
Father's `.claude/skills/`.

The source stays in this repository, where git owns it and review can reach
it. It is published by symlink into the locations each frontend scans from
any working directory:

```
DPMtF-WebUI/.claude/skills/<name>/SKILL.md      ← the source, versioned
  ├── ~/.agents/skills/<name>                    → Pi, OpenCode
  └── ~/.claude/skills/<name>                    → Claude Code, OpenCode
```

Both links are required. Claude Code does not scan `~/.agents/skills/`, and
Pi does not scan `~/.claude/skills/` unless it is added to Pi's settings.

**Verify placement rather than assuming it.** From a target project, not
from Father:

```bash
cd <target_project>
opencode debug skill | grep <name>
pi --print "List the names of the skills available to you. Names only."
```

## Writing A Frontend-Neutral Cold Start

A cold start describes what to read and what to produce. Those do not depend
on the client. Where a mechanism genuinely differs, **name all three rather
than assuming one**:

| Concern | Claude Code | OpenCode | Pi |
|---|---|---|---|
| Invocation | `/<skill-name>` | `/<skill-name>`, or a `.opencode/command/` alias | `/skill:<name>` |
| Context reset | `/clear` | `/clear` or `/new` | `/new`, or `--no-session` at start |
| mcp-light | `~/.mcp.json` | `mcp` block in the role's `opencode.json` | Pi settings or an extension |
| Tool restriction | prompt only | prompt only | `--tools` allowlist, enforced |

Two rules follow from that table.

**Never write "you are a Claude Code session" into a flow procedure.** State
the role, the flow and the contract. On 2026-08-12 a supervisor's governance
said Claude Code and `/clear`; the frontend changed to OpenCode and `/new`
the same day, and both lines had to be corrected in the same commit that
changed the database.

**A skill name is not a command name.** Frontmatter `name: Rev-Eng` is
offered by OpenCode as `/Rev-Eng` and nothing else; the lowercase `/rev-eng`
people actually type had to be added as a separate command file. Prefer
lowercase-kebab skill names so the natural invocation exists everywhere
without an alias.

## What A Flow Cold Start Must Cover

Independent of frontend:

1. **Where the state is** — one command or file that answers which run is
   active and what has been produced.
2. **Which governance sections to read**, chosen by that state, not the
   whole file.
3. **The deliverable path and the exact signal command.**
4. **The stop conditions** — what to park rather than improvise.

Supervisor cold starts add run-opening and verdict-validation. Worker cold
starts share `dpmtf-cold-start`, which covers orientation, fencing,
verification and signalling for any worker role in any flow; a flow-specific
worker skill should extend it, not restate it.

## Swapping A Frontend

The change itself is three fields and a session restart:

1. `bridge_roles.allocator_client` — via a migration, never edited by hand.
2. `bridge_roles.fresh_session_command` — see the table above.
3. `roles.yaml` in model-allocator — the `client_aliases` key must match, or
   the binding resolves to nothing rather than to a default.
4. Restart the role's tmux session. Every frontend reads its configuration
   at startup and none of them hot-reload it.

Then check the flow's cold-start skill for anything that named the old
client, and correct it in the same commit. A migration that moves the
columns and leaves the procedures describing the previous frontend produces
a role reading instructions that misdiagnose its own normal state.

## Related

- `100_BRIDGE.md` — the dispatch protocol these roles run inside.
- `22_MODEL_SELECTION.md` — which model, as distinct from which frontend.
- `16_FILE_ACCESS.md` — what a role may write.
