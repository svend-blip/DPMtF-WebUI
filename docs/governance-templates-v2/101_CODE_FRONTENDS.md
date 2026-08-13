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
| Context reset | `/clear` | **`/new`** — see below | `/new`, or `--no-session` at start |
| mcp-light | `~/.mcp.json` | `mcp` block in the role's `opencode.json` | Pi settings or an extension |
| Tool restriction | prompt only | prompt only | `--tools` allowlist, enforced |

### `fresh_session_command` Is Not A Preference

**An OpenCode role uses `/new`. A Claude Code role uses `/clear`.** The two
commands share a name and do different things, and the name is the trap.

Claude Code's `/clear` genuinely clears the conversation. OpenCode's is not
even a built-in: it resolves to `commands/clear.md` in this installation, a
*prompt* asking the model to disregard what came before. The session
continues, every token of its history continues, and the instruction is
appended to the history it asks the model to ignore. It costs window rather
than freeing it, so a role's consumption across a run is monotonic — which
matters most for exactly the roles that read files.

That file's closing line is also what caused the worst delivery failure this
project has recorded. It ends *"Treat the next user message as the
authoritative task. Reply only: Context reset acknowledged."* When the reset
and the task arrived as one message — the defect fixed in `8c36e6d` — the
model obeyed the literal instruction and did nothing else, on nine
consecutive handoffs, each rescued by a human typing "continue".

The dispatcher no longer merges them, so `/clear` is survivable again. It is
still the wrong choice, and it is already the minority: measured 2026-08-13,
25 OpenCode roles use `/new` and 2 use `/clear`. Those two are drift, not
design.

A long OpenCode session degrades in a way nobody sees. Driven past roughly
half its window on MiniMax-M3, it began emitting tool calls as prose — no
tool run, no error, finish `stop`, and a supervisor observing only silence
(see `492_REVENG_IMPLE.md` for the figures). A fresh session per handoff
removes the whole class.

**When changing this field, change it in a migration and not by hand, and
not while the role's flow has a run in flight.** It takes effect at the next
dispatch, which mid-run means a behaviour change the supervisor was not told
about.

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
