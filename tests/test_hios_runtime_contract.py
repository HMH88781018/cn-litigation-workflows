import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "hios-runtime-capability-contract.json"
PLUGIN = ROOT / ".codex-plugin" / "plugin.json"


class HiosRuntimeContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))

    def test_contract_is_pinned_to_current_public_plugin_version(self):
        self.assertEqual(self.contract["public_plugin_version"], self.plugin["version"])
        self.assertEqual(self.contract["public_repository"], "HMH88781018/cn-litigation-workflows")
        self.assertEqual(self.contract["contract_id"], "cn-litigation-workflows-hios-runtime")

    def test_every_mapped_public_skill_exists(self):
        mappings = self.contract["mappings"]
        names = {mapping["public_skill"] for mapping in mappings}
        self.assertEqual(names, {"draft-cn-element-complaints", "prepare-cn-evidence-damages"})
        for mapping in mappings:
            with self.subTest(skill=mapping["public_skill"]):
                path = ROOT / mapping["public_path"]
                self.assertTrue(path.is_file(), path)
                self.assertEqual(path.parent.name, mapping["public_skill"])

    def test_contract_forbids_silent_override_and_state_join(self):
        authority = self.contract["authority"]
        self.assertTrue(authority["no_silent_override"])
        self.assertTrue(authority["no_automatic_cross_domain_state_join"])
        self.assertIn("Current applicable law", authority["matter_specific_truth"])

    def test_contract_contains_no_client_data_channel(self):
        privacy = self.contract["privacy"]
        self.assertFalse(privacy["real_client_or_matter_data_in_public_repository"])
        self.assertFalse(privacy["real_client_or_matter_data_in_contract"])
        self.assertTrue(privacy["contract_contains_only_capability_metadata"])

    def test_legal_rule_changes_are_not_auto_merged(self):
        control = self.contract["change_control"]
        self.assertTrue(control["legal_rule_changes_must_not_auto_merge"])
        self.assertTrue(control["version_mismatch_requires_review"])


if __name__ == "__main__":
    unittest.main()
