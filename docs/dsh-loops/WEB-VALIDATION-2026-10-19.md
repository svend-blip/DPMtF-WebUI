# WEB-VALIDATION 2026-10-19 — DSH Two-Loop direkte i Web + global projektinit

Klassificering: **VERIFICERET** (målt) / **IMPLEMENTERET, MEN IKKE TESTET** /
**IKKE IMPLEMENTERET** / **BLOKERET**. Web-sessioner er ægte sessioner på
værtsprocessen (port 3080) oprettet og styret via den eksisterende
`dsh-bridge` (`create --cwd`, `send`, `status`, `wait-idle`, `cancel`).

## Aflevering (14 punkter)

1. **Ændringer:** workflow: NEEDS_DECOMPOSITION delegeres til DECOMPOSER og
   CLOSE skriver RUN.md-felter EFTER commit (script senere udvidet af God
   Father til 156 linjer med decomposer-scheduler-semantik — syntaks OK,
   NEEDS_DECOMPOSITION-need føres til decomposer, linje 51/66); skills:
   execloop (uafhængig CLOSE-verifikation, stale-claim-genoptagelse, éne
   executor pr. projekt), planloop (plan-ahead uden loft, ingen omskrivning
   af COMPLETED/BLOCKED); nyt: templatemappe + 3 globale skills i
   `~/.agents/skills`. **VERIFICERET.**
2. **Filer:** `docs/dsh-loops/execution-loop.workflow.js` (syncet til ny
   156-linjers version), `docs/dsh-loops/template/project/*` (5 artefakter,
   kanonisk), `docs/dsh-loops/DESIGN.md` (semantik opdateret),
   `~/.agents/skills/{dsh-project-init,dsh-planloop,dsh-execloop}/SKILL.md`,
   `~/.agents/skills/dsh-project-init` senere justeret af God Father
   (script holdes current — idempotens genverificeret efter). Kørte
   projekter: `dsh-loops-test` (R008–R009) og `dsh-loops-init-test` (R001).
3. **Begge loops i Web:** **VERIFICERET.** Session 1 (planning) og session 2
   (execution) kørte som separate Web-sessioner i begge projekter; init som
   tredje Web-session i init-test.
4. **Start fra WebUI:** åbn session i projektets workspace — sig
   *"Initialiser projektet med Two-Loop"* (nyt projekt), *"Start Planning
   Supervisor"* hhv. *"Start Execution Loop"*; programmatisk:
   `dsh-bridge create --cwd <sti>` + `send`. Session-model = værts-
   default (strata) — korrekt for begge sessioner; roller router eksplicit.
   **VERIFICERET.**
5. **Projektisolering:** alle loops-filer pr. projekt; workspace-hook-DB
   pr. projekt; Web-MCP-serveren for scope-mcp deler én installations-DB
   (profilet låser cwd; pr.-session-DB kræver lille mcp-mgr-ændring —
   **DOKUMENTERET BEGRÆNSNING**, jf. VALIDATION-2026-10-18-tillæg; loops
   er uafhængige heraf). **VERIFICERET** (init i to projekter uden
   krydspåvirkning; M196-DB urørt).
6. **RUN-locking/genoptagelse:** claim = status+locked_by+version+1 (ikkke
   atomisk → éksplicit éne-executor-pr.-projekt-regel); afprøvet da to
   Web-drivere blev afbrudt midt i kæder (GLM-degradering): RUN.md blev
   IN_PROGRESS, ingen commit; genoptagelse via stale-claim-reglen i samme
   sessioner førte begge RUN'er i land. **VERIFICERET.**
7. **NEEDS_DECOMPOSITION aktiverer Decomposer:** mekanismen er i
   kontrolstrukturen (script-kode, ikke prompt; need-tekst sendes til
   DECOMPOSER; nye handoffs går gennem implement→review) — **IMPLEMENTERET,
   MEN IKKE EMPIRISK UDLØST**: i R008 og R009 tog DECOMPOSER selv
   note-håndoffen under den initiale dekomponering på trods af forbud i
   RUN-beskrivelsen (model-adfærd, to gange); driveren verificerede
   proveniens via mtimes og skrev det ærligt i commit-besked/END-REPORT.
   R007's ADDITIONAL_HANDOFF er til gengæld udløst og lukket live.
8. **Supervisor ekstra handoffs:** **VERIFICERET** (R007: 03 skrevet af
   supervisor, implementeret, reviewet, CLOSE). R009-cyklus: 0 ekstra (var
   ikke nødvendig).
9. **CLOSE uafhængigt verificeret:** **VERIFICERET** — driver accepterede
   ikke struktursvar alene: R009: `git cat-file`, RUN-felter, `ls-remote` =
   sha (her uafhængigt gentaget af harness); R001-init: commit eksisterer,
   push `na` fordi `allow_push:false` (ærligt, ikke `ok`).
10. **Git commit/push:** **VERIFICERET**: `[run …]`-commits indeholder ALDRIG
    RUN.md (R001-commit viser 9 filer uden RUN.md; `??`-markeret bagefter —
    ingen bookkeeping-commit); push kun til tilladt test-remote
    (`f2adfb3` = remote-spids, ingen force); feat tilladt = `na`.
    Fejlet push er aldrig set som ok (R007's outagem var STOP→BLOCKED).
11. **Modelkald fra logs (web-fasen):** init-test: strata ×5,
    qwen35-122b-a10b-q5 ×3 (decomposer), glm45-air-iq4xs ×2 (review).
    dsh-loops-test i dag: strata ×33, qwen35 ×9, glm45 ×17 sessionsfiler —
    rolle-til-model-matrix genbekræftet i Web-kørsler. **VERIFICERET.**
12. **Tests:** bestod: init A–D,H,I,J; idempotens (2× md5-træ identical,
    også efter Opdateret skill); F,G (skills i nyt projekt); R009 Web-CLOSE
    med push; R001-init Web-CLOSE (commit only); BLOCKED-semantik (R001
    første stop); afbrudt execution + genoptagelse ×2; samtidig
    Planning+Execution; samtidige eksekveringer på tværs af projekter;
    utilgængelig/degaderet model (GLM-thinking-sløvhed + strata 503'ere —
    ingen falsk succes). Fejlede/ikke opfyldt: G's empiriske udløsning
    (pkt 7). Kendt: 14 kontraktkonflikter + R005/R007-polish (VALIDATION).
13. **Ny kode:** ingen ny service/database/plugin. Runtime-logik = det låste
    workflow (139 → Guds Faders 156-linjers version, data/skabelon).
    Mit kode-aftryk denne fase: +10 linjer i script (senere integreret),
    ~25 linjer skill-tekst, 3 SKILL.md'er (init 55), skabelondata ~55 linjer.
    Resten er markdown/dokumentation.
14. **Resterende begrænsninger:** (a) scope-mcp Web-server-delings-DB
    (dokumenteret, ubetydelig for loops); (b) G ikke empirisk udløst —
    dekomp-rolle overtager forbudt arbejde; kan skærpes i kontrakt eller
    script-håndhævelse hvis ønsket; (c) GLM-thinking-tilstand uden passthrough
    giver sene reviews under belastning (kendes fra Flow2100-plan); (d) Web-
    sessioners `wait-idle`-køring kræver ekstern overvågning (broen har
    status/cancel — brugt her); (e) ucommittede RUN.md-slutreddigelser er
    KONSTRUKTION (velges op af næste run-commit), ikke svin; (f) ingen
    produktionrørørt — commits kun i de to isolerede test-repos.

## Slut-flow (for nyt projekt)

Nyt workspace → Web-session → *"Initialiser projektet med Two-Loop"* →
Session 1 *"Start Planning Supervisor"* → Session 2 *"Start Execution Loop"*.
Ingen manuel rolle-/modelsætning; modeller i `settings.yaml`; bindinger i
`loop-config.json`; skift i workflow-kode.
