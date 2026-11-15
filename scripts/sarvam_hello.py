import os

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

response = client.chat.completions_v2(
    model="sarvam-105b",
    messages=[{"role": "user", "content": "Namaste bolo, ek line mein Hindi mein."}],
    max_tokens=1000,
)

print(response.choices[0].message.content)
