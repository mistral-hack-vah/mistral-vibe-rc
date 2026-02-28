import asyncio
import json
import websockets
import jwt
import time

JWT_SECRET = "dev-secret-change-me"
JWT_ISSUER = "voice-agent-api"

def generate_token(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "iss": JWT_ISSUER,
        "sub": user_id,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def test_ws():
    token = generate_token("test-user")
    uri = f"ws://127.0.0.1:8002/ws?token={token}&session_id=test-session"
    
    async with websockets.connect(uri) as ws:
        # 1. Test init
        print("Sending init...")
        await ws.send(json.dumps({"type": "init"}))
        resp = await ws.recv()
        print(f"Init response: {resp}")
        
        # 2. Test message
        print("Sending message...")
        await ws.send(json.dumps({"type": "message", "text": "hello agent", "images": []}))
        # No immediate response expected since acp_client is mocked/None 
        # but we can check if it doesn't crash.
        
        # 3. Test interrupt
        print("Sending interrupt...")
        await ws.send(json.dumps({"type": "interrupt"}))
        resp = await ws.recv()
        print(f"Interrupt response: {resp}")

if __name__ == "__main__":
    asyncio.run(test_ws())
