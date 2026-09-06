import asyncio
import aiohttp
import base64

async def test_imgbb_upload():
    """Test ImgBB upload with real API key"""
    
    # Your API key
    api_key = "628cdca40f5679ee5f88391122ecb513"
    
    # Sample image (1x1 pixel PNG in base64)
    image_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    
    url = "https://api.imgbb.com/1/upload"
    
    async with aiohttp.ClientSession() as session:
        form_data = aiohttp.FormData()
        form_data.add_field("key", api_key)
        form_data.add_field("image", image_data, filename="test.png", content_type="image/png")
        form_data.add_field("expiration", "600")
        
        try:
            async with session.post(url, data=form_data) as response:
                result = await response.json()
                print(f"Status: {response.status}")
                print(f"Response: {result}")
                
                if response.status == 200 and result.get("success"):
                    print("\n✅ SUCCESS! Image uploaded to ImgBB")
                    print(f"URL: {result['data']['url']}")
                    print(f"Delete URL: {result['data']['delete_url']}")
                    return True
                else:
                    print("\n❌ FAILED: Upload unsuccessful")
                    return False
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_imgbb_upload())
    exit(0 if success else 1)
