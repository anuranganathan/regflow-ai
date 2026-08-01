import os
import unittest
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv()


class TestGeminiIntegration(unittest.TestCase):

    @unittest.skipIf(not os.getenv("GOOGLE_API_KEY"), "GOOGLE_API_KEY not configured")
    def test_gemini_connectivity(self):
        try:
            client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents="Say hello"
            )
            self.assertIsNotNone(response.text)
        except APIError as e:
            # Handle rate limits or quota exhaustion gracefully in test suite
            self.skipTest(f"Live Gemini API request skipped due to API error: {e}")


if __name__ == "__main__":
    unittest.main()