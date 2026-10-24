# UCM release, trust and update policy

## Immutable core vs agent self-improvement

- **Protected core:** `skills/ucm/resources/MASTER.md`, validators and Python tools,
  schemas, P6 contracts, `release_pin.json`, and the immutable guard within `SKILL.md`.
- **Adaptive:** non-guard prose in `SKILL.md` and `adaptive/OPERATIONAL_NOTES.md`.
  These may change locally, but are advisory only and require a human semantic review.
- Runtime projects, receipts, chats, and all six paid KB sources remain **outside the
  public repository**. Do not paste the six KBs into PR descriptions or CI logs.
- Hermes self-improvement does **not** automatically update this Git repository.
  Propose changes on a feature branch, open a pull request, run CI, review the
  diff and then merge. Never push self-improvement output directly to `main`.

## Release-pin trust

The SHA-256 of the approved RC6 `release_pin.json` is:

```text
73dee756e933d74ea06c8d8ab89bd7e95d6f2e7a95452a32bacb86f202c38676
```

CI compares the candidate file against a **fixed trusted value** in its workflow
instead of recalculating the expected value from the candidate. This detects
unreviewed modifications of the release pin and protected members.

**Trust limitation:** A constant in the same Git repository is not a fully
independent trust root: a contributor who can change both the workflow and the
pin could make a malicious check pass. Before public/paid releases:

1. Protect `main` through Settings > Rules > Rulesets or Branch protection.
2. Require pull requests, at least one independent reviewer, and the
   `validate` GitHub Actions check before merge; prevent bypass where possible.
3. Optionally create repository Actions variable
   `UCM_TRUSTED_PIN_SHA256` with the approved value. It overrides the workflow
   fallback. Restrict who can edit repository settings and variables.
4. For stronger provenance, sign immutable release tags/artifacts outside
   the repository (or use signed attestations and verify with an external key).
5. Do not change the trusted pin merely to make a failing check green.

## Protected-core update workflow

1. Branch from the latest green `main`; keep `main` untouched until reviewed.
2. Change the Master, validator or schemas; revise the P6 contract origin
   master hash if applicable, run relevant tests, and intentionally regenerate
   the release pin **only for a deliberate new release**.
3. Independently inspect the resulting release-pin digest and promote that
   digest to the protected GitHub Actions repository variable through an
   authorized release process. Do not auto-promote from untrusted PR content.
4. In the PR, document changed behaviors, original test evidence and
   migration risks. Run the full suite plus live Hermes/Gemini checks.
5. Review, merge, tag the release, and distribute the CI-generated ZIP.
   Do not force-update users' installed adaptive SKILL.md or private projects.

## What CI actually verifies

- Complete Python unit discovery (`tests/test_*.py`), including anti-tamper tests.
- Integrity of pinned protected members and mandatory Standard preflight.
- Invocation availability of the P6 H01-H10 checker.
- Public ZIP packaging, exact public-file coverage, and absence of private KBs,
  film records and unintended artifacts.

CI **does not certify** semantic quality, authentic user approvals, real Google
Flow renders, Gemini/Hermes plugin registration or actual Professional KB
semantics. Those require explicit live acceptance with evidence.

## Installation and privacy

The source Skill is at `skills/ucm/`. The public portable ZIP is emitted as
artifact **UCM-Smart-Skill** on green GitHub Actions runs. Install by the
platform's documented Agent Skills mechanism; GitHub-install support varies.
Private repository installs require authorized GitHub access.
