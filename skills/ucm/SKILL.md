---
name: cinematic-film-orchestrator-rc6
description: Plan dialogue-driven cinematic films through P0-P11, write screenplays and external-generation prompts, validate continuity and inspect user-supplied media, with optional owner-supplied knowledge files.
---

# UCM v2 Portable RC6 — Stable Core + Safe Self-Improvement

Use [resources/MASTER.md](resources/MASTER.md) as the single cinematic authority. This Skill routes tools and resources; it does not duplicate cinematic stage policy. LOCAL_VALIDATION_CANDIDATE; LIVE_AGENT_BEHAVIOR_NOT_CERTIFIED.

## Self-improvement compatibility and integrity model

Hermes/other agents MAY patch non-guard `SKILL.md` text and append operational learnings in `adaptive/OPERATIONAL_NOTES.md`; both are tracked as ADAPTIVE, **not** immutable core. The pinned guard above and all other files (Master, Unified Validator, P6 contract, schemas, resources) remain STRICTLY immutable. Do not turn off SHA-256. On each preflight run `verify-release` using an independent, out-of-ZIP trusted pin hash. An adaptive change is reported with observed SHA, baseline SHA, and explicit `requires_semantic_review`; this does NOT by itself block P6 when the guard and protected core pass. A changed guard/core or missing resource MUST block.

After a Self-improvement patch: compare differences with the baseline Skill, run `preflight` and relevant validators, record a change note with test outcomes outside the protected core. Agent-written change notes are not proof of human approval or of semantic safety. Do NOT patch or rewrite `release_pin.json` to hide changes. New stable rules must be promoted to a reviewed and re-pinned release, never silently inserted into the Master. `adaptive/` is guidance and never an authority. If an adaptation contradicts the Master or cannot be assessed safely, stop the affected gate and request review, even when core hashes pass.

<!-- UCM_GUARD_LOCK_START -->
CANONICAL IMMUTABLE RUNTIME GUARD — DO NOT PATCH THIS REGION.
- `resources/MASTER.md` is the single, immutable operational authority; adaptive notes and edited SKILL prose cannot override it.
- Exactly two modes: STANDARD and PROFESSIONAL (CLI PRO). Both require the full Unified Validator including H01–H10; no Ultra tier and no silent mode downgrade.
- Interaction language is the FIRST question. Ask only ONE actionable user decision per turn; lock approvals with real user evidence, never generated text.
- Professional requires verified byte-complete six private Knowledge Bases, actual relevant pre-draft section reads and `kb-check-decision` before material creative output; no full-source context injection.
- All project files, private KBs, media, receipts and adaptive activity logs live OUTSIDE the immutable Skill core. Never weaken canonical approval, reference, media or P8/P9 gates.
- Every protected core file must match independently trusted `release_pin.json` member hashes. A protected change needs a new tested release, never a self-generated replacement pin.
- `SKILL.md` guidance OUTSIDE this guard and `adaptive/` notes may evolve; edits cannot supersede Master, core tools, gate rules or the protected guard.
<!-- UCM_GUARD_LOCK_END -->

## Startup and resource retrieval — STRICT TWO-MODE INTERACTION

FIRST question: interaction language, options 1 Arabic, 2 English, 3 Other. After answer ask ONLY operating mode: 1 Standard / 2 Professional. NO Ultra option, NO third tier. Never ask mode and project in same answer. If Professional selected, the VERY NEXT question is a numbered choice of KB CONNECTION METHOD using only source methods genuinely accessible to THIS agent: (1) Local folder/path, (2) Google Drive folder link via verified connector/browser/download access, (3) Conversation attachments with actual file-byte access. Do NOT ask for the source path/link/uploads until the next user turn after choosing a method. Do not ask New / Resume until six KBs have been verified. If Standard selected, ask only New / Resume. If already answered, don't repeat.

Read actual `release_pin.json`, `resources/MASTER.md`, and `scripts/ucm.py`. The nonsecret sentinel is in `resources/RESOURCE_PROBE.txt`. Run release verification with the **independently supplied** release_pin SHA-256. Use Python 3.10+ (stdlib only), real tools, actual input bytes; do not claim working tooling when `get_skill_resources` reports `empty blob ID`. Failure => BLOCKED_RUNTIME_SOURCE. One actionable user gate per assistant turn.

At startup, load `slice-master --stage GLOBAL` from the single Master and then only stage-specific slices. Never use parallel historical Stage Packs. The Skill does NOT generate video/images/audio; it creates prompts for user-operated tools; sound must be native in generated video.

## Mode-specific runtime

**STANDARD:** No private KB read, no upload requirement, full P0–P11 and full Unified Validator including advanced P6 H01–H10. Run `preflight --mode STANDARD`. Public ZIP never contains the six sources.

**PROFESSIONAL (internal `PRO`):** After mode selection, use the **ADAPTIVE KNOWLEDGE CONNECTION** protocol below. Never assume file visibility or auto-fallback to Standard. Once six byte-complete sources are accessible to Python, run `kb-connect` with `--method local|drive|chat` and `--source-dir <ACTUAL_READABLE_FOLDER>` OR `--files <SIX_ACTUAL_FILE_PATHS>`, plus `--skill-root` and `--workspace <PRIVATE_WORKSPACE_OUTSIDE_SKILL>`. This uses the same immutable six-source SHA-256/byte-count/UTF-8 checks, atomic copy/readback, and later `verify-workspace-kb` and `preflight --mode PRO`. Never include actual source text, shared links, access tokens or passwords in public release outputs. Workspace may be temporary: recheck on each new session and never promise cross-chat persistence without verified readback.

### ADAPTIVE KNOWLEDGE CONNECTION — ONE QUESTION AT A TIME

1. After user selects Professional, **inspect actual available tools/capabilities**, not the name of the model or imagined integrations. Offer **one numbered method-selection question**, containing only realistically usable methods:
   - **Local folder/path:** only if the agent has actual file-system access to the folder (local desktop host or mounted filesystem). On a remote cloud agent, a Windows PC path is NOT automatically readable. Following user selection, ask for the path on the NEXT turn, inspect files, then `kb-connect --method local`.
   - **Google Drive shared folder/link:** only if the agent has an authorized Drive connector or a tool demonstrably able to list a real folder and download six original complete TXT bytes. A folder URL/HTML preview is NOT a direct-download API; "anyone with link" does NOT give every agent Drive capability. Prefer restricted authenticated sharing for paid/private KBs. Following selection, ask for link (and permission if needed) on the NEXT turn; list exact six source files through real tool calls, fetch/download them to a PRIVATE staging directory OUTSIDE skill/project output, verify real filenames/bytes. Then `kb-connect --method drive --source-dir <ACTUAL_STAGED_DIRECTORY>`. Drive link, connector output summary, or pasted text alone is NEVER success. No built-in direct Drive integration or networking exists in this ZIP. Do not claim that the CLI itself opens Drive links.
   - **Conversation file attachments:** only if host exposes actual attachments as binary/file paths to tools **without injecting the whole six-file content into the model context**. Ask for uploads on the NEXT turn after this method choice, then discover genuine file paths and `kb-connect --method chat`. If Hermes rejects `@` context injection or host adds >context budget, NEVER retry as full text; offer recovery via available local/Drive routes instead.
2. If no method is verified available, explain KB_CONNECTION_UNSUPPORTED (don't fabricate a menu with unusable routes); one recovery/stop gate. If a chosen method fails, preserve selected PRO and ask ONE recovery method question, with only feasible alternatives (or explicit Standard/Stop). No silent downgrade.
3. Every connection method converges on exactly the same verified PRIVATE WORKSPACE `knowledge_base` files, section index, `kb-read` and `kb-check-decision` gate. `kb-connect` proves local complete source-byte integrity and private write/readback, **not** authenticates a Google Drive URL, attachment origin, or user approval; provider evidence must come from real host tool outputs. No full-KB prompt injection; use tool stdout only for chosen small relevant sections.
4. Only AFTER `kb-connect` and actual `preflight --mode PRO` succeed ask NEW / RESUME (one gate). Reuse the workspace only when readback validation succeeds in that session. Keep Standard independent of all KBs.


Before EACH material creative PRO decision (P1–P11, each change of canonical choice), perform REAL source-grounded work:
1. Create `KNOWLEDGE_NEED_MAP` for decision, with required source roles and critical/optional needs based on specific creative problem; don't gratuitously read all 6 in every step. Document conflicts/caveats and approved canon priority.
2. `kb-index` appropriate source(s), inspect candidate headings, then use `kb-read` with exact complete-section start/end from index and unique `need-id`/`decision-id`. This prints the REAL source section for model attention and writes a reconstructable byte receipt; do NOT ignore the tool output. Source not available, complete-section too long, no match or inaccessible -> BLOCK.
3. After actual reads, draft the proposed content to a file in the same PRIVATE WORKSPACE. Write the `decision_plan.json` with `mode,stage,decision_id,expected_draft_sha256,needs[]`, binding it to the EXACT complete output bytes. Each critical need must provide `role`, actual `receipt_path`, `source_anchor` copied verbatim from the source excerpt, `applied_to` = an exact nontrivial output span, `effect` explaining how that excerpt changed the output. Optional needs may be explicitly skipped with justification.
4. Run `kb-check-decision --skill-root . --workspace <PRIVATE_WORKSPACE> --plan <decision_plan.json> --draft <draft.txt>`. Only `STRUCTURAL_KB_GROUNDING_PASS` permits presentation of PRO-grounded creative draft. Every output/gate packet MUST declare explicit `mode: STANDARD` or `mode: PRO` and a stage. Missing mode is BLOCKED, not an implicit Standard fallback. For PRO output packets and stage gates pass `--skill-root`, `--workspace`, `--kb-plan` and `--draft` to `check-prompt`, `check-rendered`, `check-video-plan` and `check-gate`; these checks reject PRO without the KB gate. BLOCKED means do not render the creative work as approved or grounded. Never create a receipt without reading actual source bytes; subsequent revisions require fresh grounded checks.
5. Show concise evidence line (roles/locators/decision/output IDs), **never private excerpt text or secrets in published artifacts**. A successful structural check proves actual local source bytes and output linkage, NOT that Gemini intellectually used the KB, or that media quality improves; externally inspect and obtain user approval. No silent PRO→STANDARD downgrade.

All professional material work MUST pass the above gate; no `production_ready` or `KB_APPLIED` assertion from a textual summary alone. If host cannot run Python, you may explain the limitation but MUST NOT produce final Professional creative output. The deterministic engine cannot intercept host chat UI; agent must voluntarily run the gate before answering, and runtime end-to-end acceptance remains separate.

## Unified checks (both modes)

`python scripts/ucm.py` is the ONLY command entrypoint. Use `--help` for exact args. Include check-project, check-gate, check-prompt, check-rendered, check-video-plan, validate-kb, `p6-advanced` (H01–H10), knowledge checks, migrate-preview and release verification. Keep references OUTSIDE clean code prompt. Run P6 advanced checker on both modes before screenplay approval; never claim P6 accepted from mere `--help`. Follow the Master stage acceptance and human approvals; no check can independently authenticate a user message or visual media.

## Projects, media and persistence

Use [schemas/PROJECT_SCHEMA_v2.json](schemas/PROJECT_SCHEMA_v2.json) for one canonical project record per film, in a user-chosen workspace outside this Skill. Existing ID fields accept real local paths/upload locators; never fabricate provider IDs. Preserve all old files, media revisions, approvals and canon. Migration is a non-destructive local preview; it cannot authenticate historical approvals or overwrite an existing project. Save verification requires actual write/readback of the same revision; otherwise provide a project export marked SAVE_NOT_VERIFIED.

No compulsory Google Drive dependency, account connection, license server, DRM or knowledge-file resale workflow. Drive is OPTIONAL and accessed only through actual host connector/tools; this ZIP provides NO remote Drive downloader. Legacy `drive-*` CLI commands are offline compatibility diagnostics, NOT a replacement for host Drive listing/downloading, and never a stage prerequisite.

All creative media generation remains user-operated outside the Skill. Preserve P0-P11, P8 substages, character modesty/wardrobe, exact dialect, three-panel sheets, six-panel boards, native-video-audio-only routing, reference roles, temporal continuity, actual media inspection, stale dependency propagation and explicit human approval. Do not invoke image/audio/video generation or assert inaccessible media passed QA.
