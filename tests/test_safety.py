import unittest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "common"))

from safety_filter import check_metadata_safety, evaluate_ai_safety_analysis

class TestSafetySystem(unittest.TestCase):
    
    def test_clean_metadata(self):
        result = check_metadata_safety("Amazing F-35 Fighter Jet Flyover", "https://x.com/USArmy/status/123")
        self.assertTrue(result["is_safe"])
        self.assertEqual(result["action"], "allow")
        
    def test_blacklisted_keyword(self):
        result = check_metadata_safety("Horrific injury during training match", "https://x.com/USNavy/status/123")
        self.assertFalse(result["is_safe"])
        self.assertEqual(result["action"], "reject")
        self.assertIn("Blacklisted keyword detected", result["reasons"][0])
        
    def test_ai_safety_rejection(self):
        ai_output = {
            "safety_flags": ["violence"],
            "safety_actions": []
        }
        res = evaluate_ai_safety_analysis(ai_output)
        self.assertFalse(res["is_safe"])
        self.assertEqual(res["action"], "reject")
        
    def test_ai_safety_modification(self):
        ai_output = {
            "safety_flags": ["copyright_audio"],
            "safety_actions": ["mute_audio"]
        }
        res = evaluate_ai_safety_analysis(ai_output)
        self.assertTrue(res["is_safe"])
        self.assertEqual(res["action"], "modify")
        self.assertIn("mute_audio", res["modifications"])

if __name__ == "__main__":
    unittest.main()
