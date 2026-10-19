# TEMPLATE-ANALYSE — Standardisering af DSH Two-Loop til nye projekter (2026-10-18)

Read-only analyse. Intet implementeret. Mål: anbefal den absolut enkleste
metode til at anvende Two-Loop på nye projekter, med eksisterende
DSH-funktionalitet før specialudvikling.

## 1. Hvordan DSH Web håndterer nye projekter og workspaces (målt)

- Et "projekt" er simpelthen et workspace-cwd: Web-GUI'en registrerer
  workspaces automatisk (`~/.dsh/storages/workspace.json` + `session_projcache`);
  `dsh-bridge create --cwd <abs-sti>` åbner en session i ethvert katalog
  (kilde: `dsh_bridge/host.py:740` `create_session(cwd, agent_preset)`).
- **Ingen scaffold-/template-mekanisme findes for projektfiler.** DSH's CLI
  har ingen `init`; nærmeste beslægtede er *profiler*
  (`--profile <navn>`, `--from-default-profile` = skabelon for **agent-konfig**,
  ikke projektfiler) og `agentPreset` ved session-oprettelse (model/system-prompt,
  ikke filer). Konklusion: projektstrukturen skal komme fra noget, der skriver
  filer — det vil sige en **skill**, der udføres af en agent.

## 2. Indbygget mekanisme for projekt-templates? (målt)

Nej. Profiler/template-profiler dækker kun agent-konfiguration. Ingen
`dsh`-kommando, intet plugin-emne, ingen web-rute skriver projektfiler.
→ Behovet er reelt, men løses fuldt ud med eksisterende skills-mekanisme.

## 3. Hvordan dsh-planloop / dsh-execloop gøres tilgængelige for nye projekter (målt)

- Skill-rødder er **watchede** (ingen genstart) og findes i to klasser:
  - **projekt-lokale**: `<projectRoot>/.dsh/skills/` (fundament, rank 100) —
    bruger dem i dag.
  - **bruger-global**: **`~/.agents/skills/<navn>/SKILL.md`** — verificeret
    konkret: en session i `/home/svend/dsh-loops-test` har *både* projektets
    `dsh-planloop`/`dsh-execloop` og de globale (`dpmtf-cold-start`,
    `resume-work`, …) i sin katalog (talt i session-loggen).
- Projekt-lokale skills tilsidesætter globale ved samme navn (rank) —
  testspecifikke varianter kan derfor altid override'.
→ Løsning: **læg/copi `dsh-planloop` og `dsh-execloop` i `~/.agents/skills`**.
De er i forvejen projekt-agnostiske launchers (de læser alt projekt-specifikt
fra `dsh-loop/…` og `loop-config.json`). Testprojektets lokale kopier røres
ikke (kan fjernes senere, når global version er valideret).

## 4. Er ét template-repository tilstrækkeligt? Ja — og det behøver ikke være et repo

Én kanonisk templatemappe er tilstrækkelig. Anbefalet placering:
**`/home/svend/DPMtF-WebUI/docs/dsh-loops/template/`** — versioneret i
Father (gratis skriver-zone, Human-godkendelse via commit), ingen ny
genstand/service. Indhold (kopieres ind pr. projekt ved init):

| Artefakt | Indhold |
|---|---|
| `SCOPE.md` | stillads med § 1-7 (project owner udfylder) |
| `dsh-loop/RUNS-BACKLOG.md` | kolonneheader + statusnøgle, tom |
| `dsh-loop/loop-config.json` | standardrolle-bindinger (strata / p620-1 / p620-2), caps, `allow_push: false` som DEFAULT |
| `dsh-loop/execution-loop.workflow.js` | den låste kopi (139 linjer) |
| `dsh-loop/templates/RUN.md` | RUN-skabelon |

Duplicering undgås: templatet er den ene kilde; et projekts kopi er en
*instansiering*, ikke vedligeholdelses­dublet (opgradering = eksplicit
beslutning pr. projekt, jf. "må ikke ændre eksisterende RUNS").

## 5. Global `dsh-project-init`-skill — ja, det er den manglende brik

`~/.agents/skills/dsh-project-init/SKILL.md` (ren markdown, ~35 linjer,
**0 kode**):

- Udløses af "Initialiser projektet med Two-Loop" (og-lignende).
- For hvert templatem: `test -e <smål> && skip || cp` — **aldrig overskriv**;
  eksisterende `dsh-loop/`, RUNS, runs/ røres aldrig → sikker på eksisterende
  repositorier, aktivering = kun det manglende tilføjes.
- Opretter tomme kataloger (`dsh-loop/runs/`), aldrig indhold.
- Read-only tjek: providerne i `loop-config.json` findes i `~/.dsh/settings.yaml`
  (rapporter mangler — ret ALDRIG selv).
- Ingen git-handlinger (commit/init er Human-policy i eksisterende repos;
  nyt repo: brugeren/harness beslutter).
- Slutrapport: hvad er oprettet, hvad er sprunget over (allerede til stede).

Herefter virker de to loop-skills øjeblikkeligt i projektet (rødder er
watchede): "Start Planning Supervisor" / "Start eksekverings-sløjfen" i hver
sin Web-session. **Ingen manuel rolle-/modelsætning** — loop-config bringer
bindingerne, settings.yaml modellerne, workflowet routing'en.

## 6. Samlet anbefaling (rangordnet, alt med eksisterende funktioner)

1. **Anbefalet:** template-mappe i Father (punkt 4) + tre globale skills i
   `~/.agents/skills` (init, planloop, execloop). Ændringsomfang: ~5 datafiler
   + 3 SKILL.md'er, 0 kode, 0 services, 0 genstarter.
2. Forkastet — profil/preset som "projektskabelon": dækker ikke filer.
3. Forkastet — pr. projekt-kopiering af loop-skills manuelt: duplication + drift.
4. Forkastet — symlinks fra ~/.dsh ind i projekter: flytbarhed/git-problemer.
5. Forkastet — lille plugin/service for init: unødvendigt (skills-mekanismen
   er netop designet til dette).

## Beslutningspunkter (til God Father, før implementering)

1. OK at kopiere `dsh-planloop`/`dsh-execloop` til `~/.agents/skills`
   (projekt-lokale bevares midlertidigt i testprojektet)?
2. OK at oprette templatemappen under `docs/dsh-loops/template/` (Father,
   commit kræver som altid din godkendelse)?
3. `loop-config.json`-standard: `allow_push: false` som sikker standard
   (test/repo'er skal eksplicit tillade push) — OK?
4. Init skal ikke røre scope-mcp — projekt-scope ejes af Planning-sessionen
   (SCOPE.md + scope-mcp pr. projekt som hidtil) — OK?
