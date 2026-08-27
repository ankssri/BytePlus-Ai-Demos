"""
check_key.py — diagnose Seedream/Seedance auth without exposing your key.

Run from inside Seedance25_AdStudio (with your venv active):
    python3 check_key.py

It:
  1. loads .env and prints the *shape* of ARK_API_KEY (length + first/last few
     chars, and flags for stray quotes / spaces / a 'Bearer ' prefix),
  2. makes a real Seedream image call with your SEEDREAM_MODEL_ID and prints the
     HTTP status + response so you can see the exact API error.

Nothing secret is printed in full.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

key = os.getenv("ARK_API_KEY", "")
model = os.getenv("SEEDREAM_MODEL_ID", "")

print("=" * 60)
print("ARK_API_KEY diagnostics")
print("=" * 60)
print(f"  length            : {len(key)}")
if key:
    print(f"  starts with       : {key[:4]!r}")
    print(f"  ends with         : {key[-4:]!r}")
    print(f"  has leading space : {key[:1].isspace()}")
    print(f"  has trailing space: {key[-1:].isspace()}")
    print(f"  wrapped in quotes : {key[:1] in chr(34)+chr(39)}")
    print(f"  starts 'Bearer '  : {key.lower().startswith('bearer ')}")
else:
    print("  !! ARK_API_KEY is EMPTY — .env not loaded or key blank.")

print(f"\n  SEEDREAM_MODEL_ID : {model!r}")
if not model:
    print("  !! SEEDREAM_MODEL_ID is EMPTY — set it in .env (e.g. dola-seedream-5-0-pro-260628)")

if not key or not model:
    raise SystemExit("\nFix the empty value(s) above, then re-run.")

print("\n" + "=" * 60)
print("Live Seedream test call")
print("=" * 60)
url = "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
payload = {
    "model": model,
    "prompt": "a red car on a road, photorealistic",
    "size": "2K",
    "watermark": False,
}
try:
    r = requests.post(
        url,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
        json=payload,
        timeout=120,
    )
    print(f"  HTTP status: {r.status_code}")
    body = r.text
    print(f"  response   : {body[:600]}")
    if r.status_code == 200:
        print("\n✅ SUCCESS — your key + model work. The app should now generate frames.")
    else:
        print("\n❌ The API rejected this call. Read the message above:")
        print("   - 'API key format is incorrect'  -> the key value is wrong/malformed")
        print("     (use the ModelArk API Key from ai.byteplus.com/ark -> API Keys,")
        print("      region ap-southeast-1; not AK/SK; no quotes; no 'Bearer ' prefix).")
        print("   - 'model not found' / InvalidParameter -> SEEDREAM_MODEL_ID is wrong.")
except Exception as e:
    print(f"  request failed: {e}")
