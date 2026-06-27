import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

from prompts.gst_engine_prompt import GST_ENGINE_PROMPT


def process_invoice(invoice_text: str):

    prompt = GST_ENGINE_PROMPT + f"\n\nINVOICE:\n{invoice_text}"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    text = response.text.strip()

    # clean markdown if present
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)