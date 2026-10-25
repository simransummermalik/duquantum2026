import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from qpet.integrations import explain_report, record_experiment, speak_report


def sample_payload():
    return {
        "source": "test",
        "report": {
            "run_label": "Na48-Nb12",
            "pet_state": "worried",
            "status": "needs_review",
            "diagnostics": [{"code": "MEMORY_EDGE_POPULATION", "message": "Memory boundary is occupied."}],
            "metrics": {
                "Na": 48,
                "Nb": 12,
                "memory_photon_final": 4.402,
                "memory_photon_peak": 6.848,
                "target_memory_photons": 4.41,
                "peak_memory_edge_population": 0.0026,
            },
        },
    }


class IntegrationTests(unittest.TestCase):
    @patch.dict(os.environ, {"GEMINI_API_KEY": "", "BACKBOARD_API_KEY": "", "BACKBOARD_ASSISTANT_ID": "", "WATCHCAT_TIGER_DATABASE_URL": "", "ELEVENLABS_API_KEY": ""}, clear=False)
    def test_optional_integrations_have_safe_local_fallbacks(self):
        payload = sample_payload()
        explanation = explain_report(payload)
        speech = speak_report(payload)
        self.assertEqual(explanation["provider"], "local-fallback")
        self.assertIn("4.402", explanation["text"])
        self.assertFalse(speech["spoken"])

    def test_local_history_is_recorded_without_sponsor_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history.json"
            result = record_experiment(sample_payload(), destination)
            self.assertTrue(result["local"]["stored"])
            history = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(len(history["runs"]), 1)
            self.assertEqual(history["runs"][0]["reference_Na"], None)

    @patch.dict(os.environ, {"WATCHCAT_AI_PROVIDER": "openai", "WATCHCAT_AI_API_KEY": "test-key"}, clear=False)
    @patch("qpet.integrations._post_json", return_value={"output_text": "Measured explanation."})
    def test_provider_neutral_ai_explanation(self, post_json):
        result = explain_report(sample_payload())
        self.assertEqual(result["provider"], "ai")
        self.assertEqual(result["text"], "Measured explanation.")
        post_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
