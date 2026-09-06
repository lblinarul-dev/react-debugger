import asyncio
import httpx
import base64

async def test_imgbb_upload():
    """Test ImgBB upload with real API key using the same method as backend"""
    
    api_key = "628cdca40f5679ee5f88391122ecb513"
    
    # Sample image (1x1 pixel PNG)
    image_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    
    encoded_image = base64.b64encode(image_data).decode('utf-8')
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.imgbb.com/1/upload",
                params={"key": api_key},
                data={"image": encoded_image},
                timeout=30.0
            )
            
            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Response: {result}")
            
            if response.status_code == 200 and result.get("success"):
                print("\n✅ SUCCESS! Image uploaded to ImgBB")
                print(f"URL: {result['data']['url']}")
                print(f"Display URL: {result['data']['display_url']}")
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
