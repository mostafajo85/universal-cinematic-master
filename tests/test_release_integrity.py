"""UCM RC6 integrity and anti-tamper regressions. Uses only stdlib.

These tests certify file integrity/packaging behavior, NOT cinematic quality,
live Hermes/Gemini capabilities, human approvals, or KB semantic application.
"""
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
ROOT = REPO / "skills" / "ucm"
sys.path.insert(0, str(ROOT / "scripts"))
from ucm_core.portable import verify

TRUSTED_SHA = os.environ.get(
    "UCM_TRUSTED_PIN_SHA256",
    "73dee756e933d74ea06c8d8ab89bd7e95d6f2e7a95452a32bacb86f202c38676",
)


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.skill = pathlib.Path(self.temporary.name) / "skill"
        shutil.copytree(
            ROOT,
            self.skill,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    def change(self, path, old, new):
        file = self.skill / path
        original = file.read_text(encoding="utf-8")
        self.assertIn(old, original, "test fixture drift: " + path)
        file.write_text(original.replace(old, new, 1), encoding="utf-8")

    def test_trusted_baseline_is_unchanged(self):
        pin = (self.skill / "release_pin.json").read_bytes()
        self.assertEqual(hashlib.sha256(pin).hexdigest(), TRUSTED_SHA)
        result = verify(self.skill, TRUSTED_SHA)
        self.assertEqual(result["status"], "LOCAL_RELEASE_VERIFIED")
        self.assertTrue(result["adaptive"]["guard_verified"])

    def test_harmless_skill_adaptation_is_reported_and_allowed(self):
        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as f:
            f.write("\n<!-- non-authoritative operation note -->\n")
        result = verify(self.skill, TRUSTED_SHA)
        self.assertEqual(result["status"], "LOCAL_CORE_VERIFIED_WITH_ADAPTIVE_DRIFT")
        self.assertTrue(result["adaptive"]["requires_semantic_review"])
        self.assertTrue(any(x["file"] == "SKILL.md" for x in result["adaptive"]["changes"]))

    def test_harmless_adaptive_notes_are_reported_and_allowed(self):
        with (self.skill / "adaptive/OPERATIONAL_NOTES.md").open("a", encoding="utf-8") as f:
            f.write("\nProposal: shorten redundant context output; pending review.\n")
        result = verify(self.skill, TRUSTED_SHA)
        self.assertEqual(result["status"], "LOCAL_CORE_VERIFIED_WITH_ADAPTIVE_DRIFT")

    def test_immutable_skill_guard_tamper_is_rejected(self):
        self.change("SKILL.md", "Exactly two modes: STANDARD and PROFESSIONAL", "Exactly three modes: STANDARD and PROFESSIONAL")
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_SKILL_GUARD_CHANGED"):
            verify(self.skill, TRUSTED_SHA)

    def test_master_tamper_is_rejected(self):
        with (self.skill / "resources/MASTER.md").open("a", encoding="utf-8") as f:
            f.write("\n# unapproved edit\n")
        with self.assertRaisesRegex(ValueError, "RELEASE_MEMBER_HASH_MISMATCH:resources/MASTER.md"):
            verify(self.skill, TRUSTED_SHA)

    def test_validator_tamper_is_rejected(self):
        with (self.skill / "scripts/ucm_core/portable.py").open("a", encoding="utf-8") as f:
            f.write("\n# unapproved code\n")
        with self.assertRaisesRegex(ValueError, "RELEASE_MEMBER_HASH_MISMATCH:scripts/ucm_core/portable.py"):
            verify(self.skill, TRUSTED_SHA)

    def test_p6_contract_tamper_is_rejected(self):
        with (self.skill / "scripts/vendor_p6/contracts/P6_H01_H10_MASTER.json").open("a", encoding="utf-8") as f:
            f.write("\n")
        with self.assertRaisesRegex(ValueError, "RELEASE_MEMBER_HASH_MISMATCH:scripts/vendor_p6/contracts/P6_H01_H10_MASTER.json"):
            verify(self.skill, TRUSTED_SHA)

    def test_pin_tamper_is_rejected_by_external_baseline(self):
        with (self.skill / "release_pin.json").open("a", encoding="utf-8") as f:
            f.write("\n")
        with self.assertRaisesRegex(ValueError, "RELEASE_PIN_NOT_INDEPENDENTLY_TRUSTED"):
            verify(self.skill, TRUSTED_SHA)

    def test_private_sources_and_projects_are_not_in_repository(self):
        kb = ROOT / "knowledge_base"
        self.assertEqual([p.name for p in kb.iterdir()], ["README.txt"])
        self.assertFalse(list(REPO.rglob("PROJECT_RECORD.json")))
        self.assertFalse(list(REPO.rglob("SCREENPLAY.json")))
        for path in REPO.rglob("*"):
            if path.is_file():
                self.assertNotIn("__pycache__", path.parts)
                self.assertNotEqual(path.suffix, ".pyc")


if __name__ == "__main__":
    unittest.main()
