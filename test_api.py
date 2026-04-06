import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        # First try to invoke /ask
        r = await client.post("http://localhost:8000/api/ai/settings", json={"gemini_api_key": "YOUR_FAKE_KEY"})
        print(r.json())

if __name__ == "__main__":
    asyncio.run(test())
