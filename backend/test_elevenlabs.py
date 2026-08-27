import asyncio
import httpx
from app.providers.config import provider_config

async def test():
    url = f"{provider_config.ELEVENLABS_BASE_URL.rstrip('/')}/text-to-speech/{provider_config.ELEVENLABS_VOICE_ID}"

    headers = {
        "xi-api-key": provider_config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": "Hello, welcome to your AI interview.",
        "model_id": provider_config.ELEVENLABS_MODEL,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload
        )

        print("STATUS:", response.status_code)
        print("MODEL:", provider_config.ELEVENLABS_MODEL)
        print("VOICE:", provider_config.ELEVENLABS_VOICE_ID)
        print("CONTENT TYPE:", response.headers.get("content-type"))

        if response.status_code == 200:
            print("ELEVENLABS SUCCESS")
            print("AUDIO BYTES:", len(response.content))
            
            with open("elevenlabs_test.mp3", "wb") as f:
                f.write(response.content)

            print("Saved: elevenlabs_test.mp3")
        else:
            print("ELEVENLABS ERROR:")
            print(response.text[:1000])

asyncio.run(test())