import unittest
from metatron.cleanup import RuleCleaner, S1MiniConfig, S1_SYSTEM_PROMPT


class CleanupTests(unittest.TestCase):
    def test_formatting_and_fillers_without_model(self):
        c = RuleCleaner()
        d = c.route("um open ChatGPT next line YouTube dot com")
        self.assertEqual(d.text, "open ChatGPT\nYouTube.com")
        self.assertFalse(d.needs_model)

    def test_semantic_correction_wakes_model(self):
        d = RuleCleaner().route("Move it to Tuesday actually Friday")
        self.assertTrue(d.needs_model)

    def test_s1_prompt_contract_and_dynamic_budget(self):
        messages = S1MiniConfig.messages("um send the report friday")
        self.assertEqual(messages[0]["content"], S1_SYSTEM_PROMPT)
        self.assertTrue(messages[1]["content"].startswith(
            "[Styling: semi-formal] [Structure: prose] [Context: general]\n"
        ))
        self.assertEqual(S1MiniConfig.output_budget(100), 162)
        self.assertEqual(S1MiniConfig.output_budget(1000), 1024)
        with self.assertRaises(ValueError):
            S1MiniConfig.control_line(styling="invented")


if __name__ == "__main__":
    unittest.main()
