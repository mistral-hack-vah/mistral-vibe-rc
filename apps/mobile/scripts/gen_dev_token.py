#!/usr/bin/env python3
"""Generate a long-lived dev JWT token for mobile app development."""

import os
import sys
import time

# Add project root to path so we can read the same config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

try:
    import jwt
except ImportError:
    print("Install PyJWT: pip install pyjwt")
    sys.exit(1)

SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
ISSUER = os.environ.get("JWT_ISSUER", "voice-agent-api")

payload = {
    "sub": "dev-user",
    "iss": ISSUER,
    "iat": int(time.time()),
    "exp": int(time.time()) + 365 * 24 * 60 * 60,  # 1 year
}

token = jwt.encode(payload, SECRET, algorithm="HS256")
print(f"\nDev JWT Token (valid 1 year):\n\n{token}\n")
print("Add to apps/mobile/.env:")
print(f"EXPO_PUBLIC_JWT_TOKEN={token}")
