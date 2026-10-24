# Universal Cinematic Master — UCM v2 RC6

One portable Agent Skill with one canonical Master, unified validation tools, optional external/private cinematic knowledge and an adaptable operational layer.

## Privacy and intended use

This repository intentionally contains **no private Knowledge Base documents**, customer data, film projects, credentials, or approval logs. Keep purchased/private KB documents and individual film projects outside this repository.

## Install

Install `skills/ucm/` using the supported Agent Skills installation method in your agent. Platforms differ: not every agent supports installation directly from a Git repository. For platforms that require ZIP import, download the `UCM_Smart_Skill.zip` artifact from a successful GitHub Actions build, or create a ZIP of the *contents of `skills/ucm`*, with `SKILL.md` at ZIP root.

## Modes

- **STANDARD**: no external knowledge files required.
- **PRO**: select a supported KB connection method (local, connected Drive or downloadable attachments), validate original bytes, then retrieve only necessary sections. Never inject the six full KB documents into conversation context.

## Test locally

Python 3.10+:

```bash
python scripts/ucm.py --help
```

Run from `skills/ucm`; CI also executes `python -m unittest discover -s tests -p 'test_*.py' -v` from the repository root, enforces a pinned trusted release digest, runs Standard preflight and builds a verified public ZIP.

## Releases and self-improvement

`resources/MASTER.md`, validators, schemas and protected governance files must be changed only through a tested, reviewed commit and a refreshed signed-off release. Operational learning belongs in `adaptive/` and must not silently bypass any validator gate. Local patches do not automatically sync to GitHub. Use a branch and pull request; do not push patches directly to main. See [the release, trust, and update policy](docs/RELEASE_AND_UPDATE_POLICY.md). The workflow's pinned trust value is only as strong as branch/repository protection; configure required CI checks and review for `main` before production releases.

**RC6 is a release candidate.** Local checks are not proof of live functionality in Hermes/Gemini.

## GitHub Actions and portable install

After a successful Actions run, open that run's **Artifacts** section and download `UCM-Smart-Skill`; the contained `UCM_Smart_Skill.zip` has `SKILL.md` at its root. Install it using your agent's native skill manager or ZIP importer. This private repository needs authenticated access; universal automatic GitHub installation is **not** guaranteed for all agent platforms.

Hermes self-improvement can modify installed adaptive prose locally, but these changes do **not** push themselves to GitHub. To publish a change, review the diff on a branch, run the full CI suite, and merge by PR. Keep film projects and the six KB source texts outside the repository.
