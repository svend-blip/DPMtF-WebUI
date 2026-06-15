# 19 — OFFLINE MODE

> **en-US is the standard language for all governance-templates-v2 files.**

## Purpose

Defines how the DPMtF governance loop operates without internet connectivity.
Local git is the source of truth; remote operations are deferred until online.

## When to Use

- **All roles:** When internet is unavailable.
- **Architect:** When selecting models for tasks (offline = local model only).
- **Human:** When authorizing commits (local only, push deferred).

---

## Offline Operation Rules

1. **Local git is the source of truth** — all commits are local.
2. **Push is deferred** — mark as pending in [[27_NEXT_CONTEXT]].
3. **Local model is default** — no cloud model access when offline.
4. **Bridge operates locally** — tmux sessions are local, bridge.py works without internet.
5. **No external API calls** — all operations are local.
6. **Governance files are fully available** — they are local files.

## Model Selection When Offline

| Condition | Model |
|-----------|-------|
| Internet available + complex task | Cloud model (per [[22_MODEL_SELECTION]]) |
| Internet available + simple task | Consider local model (cost: 0 EUR) |
| Offline | Local model only |

## Commit Flow When Offline

```
1. Review validates changes → passes
2. Human authorizes commit
3. git commit executed locally
4. Push marked as pending in [[27_NEXT_CONTEXT]]
5. When online: sync recovery per [[15_GIT_POLICY]]
```

## Sync Recovery (When Back Online)

1. Check unpushed commits: `git log origin/master..master --oneline`.
2. Review unpushed commit messages.
3. Human authorizes push: `git push origin master`.
4. Update [[27_NEXT_CONTEXT]] — remove pending marker.

## Bridge Operation When Offline

The bridge (`bridge.py`) operates entirely on local tmux sessions:

- `claude_architect` — local only when offline.
- `claude_implementer` — always local.
- `claude_review` — local only when offline.

All bridge commands work without internet: `send`, `complete`, `ask-architect`,
`answer-review`, `next-id`.

## Model Downloads

- Model downloads are one-time setup — require internet for initial download.
- Subsequent use is fully offline.
- Adding new local models requires internet + Human approval.

---
