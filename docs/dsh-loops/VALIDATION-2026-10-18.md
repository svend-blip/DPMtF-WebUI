# VALIDATION — DPMtF two loops in DeepSeek Harness Web

Date: 2026-10-18 · Isolated vehicle: `/home/svend/dsh-loops-test` (own bare
test remote `/home/svend/dsh-loops-test-remote.git`) · Design:
`docs/dsh-loops/DESIGN.md`. Execution results below are appended as measured;
this report closes when they are complete.

## 1. DSH functions reused (nothing re-implemented)

- Workflow engine (`dsh-tool-workflow`): locked JS script, `agent()` with
  explicit `provider`/`model`/`schema`; caps and stop states as code.
- Subagents (`dsh-subagent-spawn/fork-in-process`): every role is a real
  child execution with its own session log (`request/header →
  data.header.config.provider|model`).
- Provider routing (`dsh-llm-pi-ai`): routes in `~/.dsh/settings.yaml`;
  settings re-read per request (no restart).
- Sessions: `dsh --profile headless` per project (= Session 1 / Session 2),
  `agent-default-model` for the session model, per-call override for roles.
- Skills (`dsh-skill-filesystem`, `<projectRoot>/.dsh/skills/`), goals,
  MCP (`mcp-light` read-only, `scope-mcp` checkpoints), shared workspace and
  git via the agents' own bash.
- DPMtF assets reused unchanged: the four governance contracts (read by each
  role at run time via absolute path), the run-directory file convention
  (`RUN.md`, `NN-handoff.md`, `NN-result.md`, `NN-verdict.md`,
  `END-REPORT.md`, `RUNS-BACKLOG.md`), mcp-light (read-only verified: all 36
  tools are get/find/search/validate/list/suggest; every DB open `mode=ro`).

## 2. Files & configuration changed/created

Father (DPMtF-WebUI) — new, under `docs/dsh-loops/` (docs = free-write zone;
nothing else touched, no commit without Human approval):
`DESIGN.md`, `execution-loop.workflow.js` (locked artifact), `RUN.md`
template facts, `contract-analysis-supervisor-decomposer.md`,
`contract-analysis-implementor-review.md`, this report.

DSH config (`~/.dsh`, backed up first):
- `settings.yaml`: + `llamacpp-p620-1` (qwen35-122b-a10b-q5 @
  omarchy-1:8443), + `llamacpp-p620-2` (glm45-air-iq4xs @ omarchy:8443).
  Existing providers untouched. Backups: `settings.yaml.backup-before-p620`.
- `.credentials.yaml`: + refs `P620_1_LOCAL_API_KEY: dummy`,
  `P620_2_LOCAL_API_KEY: dummy` (keyless llama.cpp still requires a
  resolvable key ref; the Authorization header is ignored by the server).
  Backup: `.credentials.yaml.backup-before-p620`.

Test project `/home/svend/dsh-loops-test` (isolated, NOT production):
`SCOPE.md`, `dsh-loop/loop-config.json`, `dsh-loop/execution-loop.workflow.js`,
`dsh-loop/templates/RUN.md`, `.dsh/skills/dsh-planloop/SKILL.md`,
`.dsh/skills/dsh-execloop/SKILL.md`, runs created by the planning session.

## 3. How Session 1 (Planning Supervisor) starts

```
cd <project>   # e.g. /home/svend/dsh-loops-test
dsh --profile headless "You are the Planning Supervisor session … follow the
dsh-planloop skill …"      # or any DSH session loading .dsh/skills/dsh-planloop
```
Model comes from `agent-default-model` (strata-local /
qwen3.8-flash-next-gptq-nvfp4). Verified: planning run logged 30× that
provider/model pair.

## 4. How Session 2 (Execution) starts

```
cd <project>
dsh --profile headless "You are the Execution session … follow the dsh-execloop skill …"
```
The driver claims the next READY RUN and invokes the DSH workflow tool with
`dsh-loop/execution-loop.workflow.js` VERBATIM — chain order is code, not
prompt. It repeats automatically until no READY RUN is claimable.

## 5. How RUNs are shared between the sessions

Files only (verified sufficient; no new database/service):
`SCOPE.md` + `dsh-loop/runs/RNNN-<slug>/RUN.md` (canonical state) +
`dsh-loop/RUNS-BACKLOG.md` (planning index). Planning is sole writer of
DRAFT/READY runs; execution claims READY → IN_PROGRESS (`locked_by`,
`version`+1); Planning must not edit IN_PROGRESS runs (Amendment-requests
section instead). Existing DPMtF file convention reused; mcp-light is
read-only; the DB has no table with the required fields (audited).

## 6. How handoffs are created and processed

`EXECUTION_DECOMPOSER` (p620-1) turns RUN.md into `NN-handoff.md` (purpose,
fence, deliverables, acceptance, tests, dependencies, constraints).
Per handoff, sequentially: `IMPLEMENTOR` (strata) writes `NN-result.md` +
code inside the fence; `REVIEW` (p620-2) measures the tree itself and writes
`NN-verdict.md` (APPROVED|REJECTED, Evidence mandatory) and returns a
structured verdict (`schema`) with `routing` for rework. REJECTED returns to
implementor or decomposer per routing, bounded by
`caps.max_rework_per_handoff`; exhaustion ⇒ run BLOCKED, never COMPLETED.

## 7. How the Execution Supervisor creates extra handoffs

After the queue drains, the supervisor (strata, SUPERVISOR_PLANNING role,
current RUN only, `schema`-typed) decides `CLOSE | ADDITIONAL_HANDOFF |
NEEDS_DECOMPOSITION | BLOCK`; it writes new `NN-handoff.md` files itself
(≤ `caps.max_extra_handoffs`, total ≤ `caps.max_total_handoffs`) or asks for
one sub-decomposition (≤ `caps.max_supervisor_rounds`), then the loop
re-runs implement→review for the added handoffs and returns to the
supervisor. It never creates RUNs.

## 8. How git commit/push is handled

Only the Execution Supervisor writes git: after re-measuring all verdicts
and acceptance criteria, it stages this run's in-fence files only, commits
`[run RNNN] <objective>` (English, RUN-ID per SP §cadence), and pushes ONLY
if `loop-config.git.allow_push` is true (test remote only here), never
force, never another branch. `push` is recorded honestly as
`ok|failed|denied|na` — a failed push is never recorded as ok. Chain roles
keep git read-only per contracts. No production repo receives commits
without Human approval.

## 9. Model shifts verified (measured, not asserted)

Via `zstd -dc ~/.dsh/sessions/<cwd-slug>/<uuid>/session.v3.jsonl.zstd |
grep '"provider":…"model":…'` (field `request/header →
data.header.config`):
- Planning session: 30× `strata-local / qwen3.8-flash-next-gptq-nvfp4`.
- Execution driver session: strata-local (host model).
- Decomposer child (live during R001): `llamacpp-p620-1 / qwen35-122b-a10b-q5`.
- (implementor/review/supervisor rows: appended below as the run completes)

## 10. Tests performed

- Error handling (observed live in cycle 4, first attempt): a REVIEW child
  died mid-run (transient P620 #2 outage) → `agent()` resolved null → the
  locked script returned `STOPPED role=review` → driver reconciled the RUN
  to BLOCKED with the role+detail as reason — NO commit, work-in-progress
  preserved, never COMPLETED on a stop. Unblocked and re-driven by the
  harness after verifying the endpoint (200) — the stop is recoverable by
  design because all state lives in files.
- Push-denial path (`allow_push: false`) is enforced in the script and the
  supervisor prompt; in this validation every RUN pushed to the ONE
  explicitly-allowed test remote — production repos received no commits or
  pushes (verified: DPMtF-WebUI tracked files unmodified by this task,
  nothing committed there).

- Route probes: 3 explicit routes return; negative probe (unknown model id)
  stops the role with null child ⇒ workflow STOPPED (explicit stop state).
- Schema probe: verdict schema enforced by the engine (enum must carry
  `type` — engine subset requirement).
- Planning session produced 3 RUNs with RED-before-run acceptance criteria
  (contract discipline observed; rehearsal green noted in its ledger).
- Execution: full chain results appended below.

## 11. What is still missing / limitations (documented, honest)

- `dsh web` GUI sessions share ONE scope-mcp server db (profile pins cwd to
  the install dir); per-project isolation works for headless processes —
  fixing the web profile needs a `dsh web` restart, deliberately deferred
  (running sessions preserved). Web-session loop operation therefore keeps
  project truth in files (§5), not in scope-mcp.
- Child agents inherit session hooks (generic "call status" hints reach
  them); role prompts pin their task explicitly — observed workaround.
- GLM non-thinking (`enable_thinking: false`) is NOT sent (DSH provider layer
  has no chat_template_kwargs passthrough; measured as open point from the
  Flow2100 plan). Review works; noted.
- Contract conflicts (27 total, cited) are NOT fixed by editing governance;
  the runtime overlay in role prompts re-anchors BridgeV002 mechanics
  explicitly. A DSH-variant of SUPERVISOR_PLANNING (extra-handoff authority +
  commit authority for the Execution Supervisor; cap-hit≠COMPLETED) is the
  one item that would deserve a governance edit later — deliberately not
  done now (Human approval zone).
- Rework overwrites `NN-verdict.md` (final verdict only; the REJECTED text
  is not kept on disk — the workflow return value and ledger carry it).
  Polish item: append-only verdict history (e.g. `NN-verdict-2.md`).
- A CLOSE commit can capture RUN.md mid-state; the driver reconciles and
  bookkeeping-commits afterwards (honest, observed in R007). Polish item:
  have the supervisor write final RUN.md fields before committing.
- `allow_push: false` (denied-push path) is enforced in script+prompt but
  was not exercised in runs — every test push went to the one explicitly
  allowed test remote. Production repos: no commits/pushes without Human
  approval, none made.
- The driver loop runs "until no READY RUN" inside one session; indefinite
  unattended service would be a per-session goal/loop wrapper — deliberately
  not built (minst mulig udvikling).
- scope-mcp: Planning uses it per-project (headless cwd); the split for web
  sessions is documented above. No existing project data changed (M196 db
  untouched — measured).

All FASE 5 test points from the task are therefore covered: two independent
DSH sessions; planning produces RUNs; execution takes READY runs; correct
model per role (log-verified); real subagent executions; correct handoff
order; REJECTED loop (2× real rejections, routed); supervisor-created extra
handoff (R007 #03, forced by control rule); APPROVED + RUN closure with
git commit/push to an explicit test remote; persistence across sessions
(file-backed; BLOCKED→re-drive survived process restarts); no production
project changes; child-failure and cap/stop states handled explicitly.

## 12. Lines of new code

- Locked workflow script (the ONLY new executable logic):
  `docs/dsh-loops/execution-loop.workflow.js` — 129 lines (≈111 non-comment).
- Configuration artifacts: `loop-config.json` 13 lines; `RUN.md` template
  41 lines; two role skills 36 + 32 lines (prompt/instruction content).
- Documentation (not code): DESIGN 196, two contract analyses 125 + 98,
  this report.
- New services/databases/allocators/WebUI/plugins installed: **zero**.
  Kernel changes: none (DSH untouched; only `~/.dsh` config + credential
  refs). DPMtF runtime code: untouched.

## Execution results (appended as measured)

### Cycle 1 (driver headless session, 17:52–19:00, test remote only)

| Run | Final status | Commit | Push | Verdicts |
|---|---|---|---|---|
| R001-subtract | COMPLETED (workflow CLOSED) | `73a0073` | ok (verified on remote) | 01 APPROVED, 02 APPROVED (rework 0) |
| R002-reverse | BLOCKED (STOPPED at execution_decomposer) | — | none | none — stopped before review |
| R003-divide | COMPLETED (workflow CLOSED, depends_on R001 honored) | `6b12a90` | ok (verified on remote) | 01 APPROVED, 02 APPROVED (rework 0) |

Evidence highlights:
- Commit `[run R001-subtract] …` staged in-fence product files + run record
  only; excluded `__pycache__` and `.scope-mcp` sidecars; supervisor
  re-measured both acceptance commands before CLOSE (independent re-run by
  the harness afterwards: 3 + 6 tests OK).
- R002: the decomposer returned its no-escalation note as a prose string and
  the locked script's strict `'none'` sentinel stopped the chain — an
  EXPLICIT STOPPED state, reconciled to BLOCKED with role+detail in the
  ledger, never COMPLETED (cap/stop≠COMPLETED guarantee observed for real).
  Harness fix: prefix-tolerant `none` sentinel + tightened decomposer prompt;
  R002 unblocked and re-driven in cycle 2.
- Driver stopped automatically when no READY RUN remained; two-consecutive-
  STOPPED rule never triggered (R003's CLOSE broke the streak).

Model identity matrix (child session logs, `request/header →
data.header.config`):

| Role | Provider/model | Requests |
|---|---|---|
| EXECUTION_DECOMPOSER | `llamacpp-p620-1/qwen35-122b-a10b-q5` | 38 + 23 |
| IMPLEMENTOR | `strata-local/qwen3.8-flash-next-gptq-nvfp4` | 44 + 26 |
| REVIEW | `llamacpp-p620-2/glm45-air-iq4xs` | 83 + 53 |
| EXECUTION SUPERVISOR | `strata-local/qwen3.8-flash-next-gptq-nvfp4` | 56 |
| Planning session (Session 1) | `strata-local/qwen3.8-flash-next-gptq-nvfp4` | 30 |
| Execution driver (Session 2) | `strata-local/qwen3.8-flash-next-gptq-nvfp4` | 18 |

### Cycle 2 (controls: re-drive after fix; rework loop; sentinels) — driver headless, all COMPLETED

| Run | Final status | Commit | Push | Verdicts |
|---|---|---|---|---|
| R002-reverse (re-drive) | COMPLETED (CLOSED, 1 supervisor round) | `ca9c025` | ok (remote verified) | 01 APPROVED first pass — sentinel fix proven |
| R004-negate | COMPLETED (CLOSED, 1 supervisor round) | `e6417ed` | ok (ls-remote verified) | 001 APPROVED first pass |
| R005-join | COMPLETED (CLOSED, 1 supervisor round) | `a07253e` | ok (ls-remote verified) | 01 **REJECTED → APPROVED after 1 rework**; 02 **REJECTED** (README-skeleton violation) **→ APPROVED after 1 rework** |

- **REJECTED-loop proven with routing:** both R005 rejections routed to
  IMPLEMENTOR (proven by chain composition: the 10-agent workflow contained
  no decomposer-revise call), each fixed within `max_rework_per_handoff: 2`.
  Verdict files hold only the final APPROVED version (rework overwrites —
  noted as a polish item: an append-only verdict history would preserve the
  rejected text; not required by the contracts).
- Planning-side control worked live: the planning session REJECTED my
  deliberately contradictory third acceptance command for R004 (measured it,
  ruled it impossible, recorded the ruling in the ledger instead of shipping
  an unclosable RUN) and serialized R005→R002 / R006→R005 on shared-file
  dependencies without being asked.
- Post-run RUN.md bookkeeping deliberately stays out of the RUN commit;
  a harness chore commit keeps the tree clean (`__pycache__`/scope dirs
  untracked, `.gitignore` added).
- Independent harness check after cycle 2: `python3 -m unittest discover`
  → 15 tests OK; remote master = `a07253e`.

### Cycle 3 (R006-titlecase, handoff-count forcing) — COMPLETED

Closed with commit `774b708` (push ok, remote verified), verdicts 01/02/03
all APPROVED (0 rework). Outcome of the forcing test: the DECOMPOSER wrote
three handoffs itself (implementation / tests / read-only integration
verification), satisfying the `>= 3` counting criterion before any
supervisor round — supervisor rounds: 1 (CLOSE), additions: 0. Honest
conclusion: our decomposer over-covers acceptance instead of under-covering;
the supervisor ADDITIONAL_HANDOFF branch remained untriggered.

### Cycle 4 (R007-pad, control-rule forcing) — first attempt

Revealed the child-failure control for real: the REVIEW child died
(transient P620 #2 outage) => null => STOPPED role=review => RUN honestly
BLOCKED (no commit, work-in-progress preserved, reason = returned
role+detail). Recoverable by file-state design; endpoint verified 200
before re-drive.

### Cycle 5 (R007 re-drive) — supervisor ADDITIONAL_HANDOFF proven live

The decomposer created only 01-handoff.md (pad) and 02-handoff.md
(PadTests) — the control rule held: no handoff for EXTRA-NOTE.md. In
supervision round 1 the EXECUTION SUPERVISOR wrote 03-handoff.md itself
(recorded as "supervisor addition 1 of 3, totals 3 of 8"),
implement->review APPROVED it, and round 2 CLOSED the run: commit 9fe05c0
+ reconciliation commit 28542e8 (the driver honestly noted the run commit
had captured RUN.md mid-state and corrected it), both pushed (no force).
test -f .../EXTRA-NOTE.md measures green.

### Final queue state (all measured)

| Run | Status | Commit | Push | Notable control proven |
|---|---|---|---|---|
| R001-subtract | COMPLETED | 73a0073 | ok | first full chain, 2 handoffs |
| R002-reverse | COMPLETED | ca9c025 | ok | stop -> BLOCKED -> unblock -> re-drive |
| R003-divide | COMPLETED | 6b12a90 | ok | depends_on honored, auto-continue |
| R004-negate | COMPLETED | e6417ed | ok | planning rejected a contradictory criterion |
| R005-join | COMPLETED | a07253e | ok | 2x REJECTED -> rework -> APPROVED |
| R006-titlecase | COMPLETED | 774b708 | ok | decomposer over-coverage; harness criterion repair |
| R007-pad | COMPLETED | 9fe05c0 | ok | child-failure stop + supervisor-added handoff |

Final independent checks: python3 -m unittest discover -> 25 tests OK;
all 7 RUN.md files COMPLETED with commit + push: ok; test tree clean;
origin/master = local HEAD; no production repo received commits or pushes
(DPMtF-WebUI tracked files unmodified by this task; ~/.dsh changes are
configuration only, additive, with backups).





---

## Tillæg (web-fasen, 2026-10-18 aften): scope-mcp-workspace-isolering — konklusion

Målt adfærd (alle tre kilder er enige):
- MCP-serveren for scope-mcp er ÉT stdio-barn under `dsh web`-processen med
  cwd låst til `/home/svend/scope-mcp` (profilet `cordis.patch.yml`,
  `env: {}`) → alle Web-sessioner på værtsprocessen deler
  `/home/svend/scope-mcp/.scope-mcp/state.db`. Direkte bevis: denne Web-sessions
  `scope-mcp status`-kald viser M196-projektet (installations-dben), selvom
  workspacet er DPMtF-WebUI — mens hooks (auto-checkpoint/resume-brief)
  skriver til workspace-dben. Splitten er altså reel i Web-sessioner.
- Opslagsrækkefølgen i `scope-mcp/src/state.js:27-30`: `SCOPE_MCP_DB` (env)
  ellers `{cwd}/.scope-mcp/state.db`; db'en låses pr. proces ved start —
  pr. session-skift eksisterer ikke i serveren.

Konklusion for kravene i §4:
- Konfigurationsmulighederne er udtømte: én global `SCOPE_MCP_DB` kan ikke
  isolere flere samtidige projekter (kravet siger eksplicit, at én global
  variabel er utilstrækkelig); profil pr. projekt kræver én DSH-proces pr.
  projekt (ikke tilladt her: samme WebUI på 3080 skal bruges); at fjerne
  cwd-låsen i profilet giver stadig én fælles db for alle sessioner i
  processen og kræver genstart (nægtet uden eksplicit godkendelse).
- PR PER SESSION isolering i Web er derfor IKKE MULIGT med nuværende
  mekanisme (kræver lille ændring i mcp-mgr: spawn pr. session med
  session-cwd eller injicer `SCOPE_MCP_DB`) — dokumenteret begrænsning,
  ingen kode ændret.
- Projektisolation opretholdes alligevel, hvor det tæller: RUN-backlog,
  RUN.md, SCOPE.md og alle roles artefakter er filer i projektet (sandhed
  pr. projekt); hooks og headless-processer resolverer korrekt pr.
  workspace (verificeret: testprojektets egen `.scope-mcp/state.db`
  opstod, M196-dben er urørt — kun læst).
- Web-sessioners scope-mcp-VÆRKTØJER (init_project/set_goals) bør derfor i
  loop-regi kun bruges eksplicit og bevidst (delelt projekt-slot) —
  loop-reglerne i skills kræver dem ikke.


### Cycle 6 (R008-round, NEEDS_DECOMPOSITION-semantik, opdateret script)

CLOSE-den-grænse afprøvet med de nye regler: commit `6667399` indeholder
KUN in-fence filer — **RUN.md er korrekt ekskluderet** (ingen mid-state i
committen); driveren verificerede uafhængigt (cat-file, ls-remote fast-forward)
og lignede **ingen bookkeeping-commit** (RUN.md-redigeringen forbliver
ubevidst ucommittet). Approvals 2×0 rework; kriterier grønne.

Ærligt kernfund: dekompereren skrev **igen** note-leverance-håndoffen i den
INITIELLE dekomponering (mtimes 06:48/06:49Z, før første resultat), på trods
af forbuddet i RUN-beskivelsen — superviserens 1. runde lukkede derfor
straks, og NEEDS_DECOMPOSITION-ruten blev ikke udløst. Commitemnes påstand
om ruten var falsk; **driveren opdagede det via file-mtime-proveniens og
korrigerede RUN.md i append-only ledger** (COMPLETED står, da kriterierne
reelt er mødt). G = IMPLEMENTERET, MEN IKKE EMPIRISK UDLØST — nyt
forceringsforsøg: R009-truncate i Web-fasen (cyklus 7).


---

## Web-fasen (2026-10-19 formiddag): to rigtige DSH Web-sessioner paa port 3080

Transport: `dsh-bridge` (eksisterende CLI) — `create --cwd <projekt>` aabner
autentisk Web-session; `send`/`wait-idle`/`status`/`cancel` styrer den.
Session-modellen er vaertens `agent-default-model` (strata) — korrekt for
Planning/Execution; roller router fortsat eksplicit i workflowet.

### Global Two-Loop-init (godkendt 1-4) — VERIFICERET i Web
Nyt isoleret projekt `/home/svend/dsh-loops-init-test` (egen SCOPE.md-
markoer + git i forvejen):
- A: `dsh-project-init` synlig i WebUI-et uden genstart (watched roots).
- B: "Initialiser projektet med Two-Loop" i en Web-session oprettede
  strukturen; loop-configs `<WORKSPACE>` blev udskiftet til den reelle sti.
- C: gentaget init — checksum-trae 1:1 identisk (md5), 0 filer aendret
  (idempotens haardt maalt, ikke paastaaet).
- D: eksisterende SCOPE.md SKIPPED/urort (sessionens egen rapport + indhold).
- H/I/J: provider-tjek read-only OK; ingen services/plugins; ingen genstart.
- F: Planning-session (Web, strata) udviklede SCOPE.md og oprettede
  R001-shout READY med koerbare kriterier; ejermarkoer bevaret i SCOPE.md.
- E: eksisterende RUNS i dsh-loops-test urorte gennem alt.

### Samtidig Planning og Execution — VERIFICERET
Planlaegningssessionen i dsh-loops-test (R009) korede parallelt med
execution-sessioner i begge projekter uden faelle filkonflikt (projekterne
adskilte; én executor pr. projekt haandhaevet).

### Model-degradering og afbrydelse (R009/R001-kæderne)
GLM-endpointen gik i lav-throughput thinking-tilstand midt i to parallelle
reviews; DSH's child genpruede internt 22x300 s uten fremdrift.
 Intervention: `dsh-bridge cancel` paa begge execution-sessioner = aegtes
afbrydt Execution. RUN.md'erne blev korrekt IN_PROGRESS (ingen COMPLETED,
ingen commit) — stale-claim-genoptagelse paafoert i samme sessioner.
RESULTAT (cyklus 7, samlet): begge kaeder gennoertog via stale-claim-reglen.
R009-truncate CLOSE fra Web-session: commit f2adfb3, push ok (remote = sha),
RUN.md udeladt af commit, ingen bookkeeping-commit; driveren dokumenterede
proveniens: NEEDS_DECOMPOSITION blev IKKE udløst (decomposer tog
note-haandoffen selv — 2. gang), aendret tilstands-aenderet forloebsdomet i
END-REPORT. R001-shout (init-test) BLOCKED -> genoptaget -> COMPLETED:
commit 0ae2588, push "na" (allow_push false), RUN.md uden for commit.
Alt detaleret i WEB-VALIDATION-2026-10-19.md.
