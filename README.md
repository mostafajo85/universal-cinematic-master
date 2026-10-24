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

Run from `skills/ucm` or use the scripts in `.github/workflows/` for complete checks.

## Releases and self-improvement

`resources/MASTER.md`, validators, schemas and protected governance files must be changed only through a tested, reviewed commit and a refreshed signed-off release. Operational learning belongs in `adaptive/` and must not silently bypass any validator gate. Local patches do not automatically sync to GitHub. Use a branch and pull request; do not push patches directly to main.

**RC6 is a release candidate.** Local checks are not proof of live functionality in Hermes/Gemini.
