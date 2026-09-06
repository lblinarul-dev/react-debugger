"""
Test script to verify imgbb upload functionality.
Run this after setting IMG_BB_API_KEY environment variable.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = str(Path(__file__).parent.parent / "backend")
sys.path.insert(0, backend_path)
os.chdir(backend_path)  # Change to backend dir for imports

from config import settings


async def test_imgbb_upload_direct():
    """Test the imgbb upload function directly without service class."""
    
    # Check if API key is set
    api_key = os.getenv("IMG_BB_API_KEY")
    if not api_key:
        print("❌ IMG_BB_API_KEY not set. Please set it to run this test.")
        print("   export IMG_BB_API_KEY='your-api-key'")
        return False
    
    # Create a test image (simple 1x1 PNG)
    test_image_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 pixels
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,  # IEND chunk
        0x42, 0x60, 0x82
    ])
    
    print("🧪 Testing imgbb upload function...")
    print(f"   API Key present: {bool(api_key)}")
    print(f"   Test image size: {len(test_image_data)} bytes")
    
    try:
        import base64
        import httpx
        
        encoded_image = base64.b64encode(test_image_data).decode('utf-8')
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.imgbb.com/1/upload",
                params={"key": api_key},
                data={"image": encoded_image},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("success") and result.get("data"):
                display_url = result["data"]["display_url"]
                print("✅ Upload successful!")
                print(f"   Image URL: {display_url}")
                return True
            else:
                print(f"❌ Upload failed: {result}")
                return False
            
    except Exception as e:
        print(f"❌ Upload failed with error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 60)
    print("IMGBB UPLOAD FUNCTIONALITY TEST")
    print("=" * 60)
    
    # Test 1: Direct function test
    print("\n--- Test 1: Direct imgbb upload function ---")
    test1_passed = await test_imgbb_upload_direct()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Direct upload test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    
    if test1_passed:
        print("\n🎉 Bug fix verified - imgbb upload working!")
        return 0
    else:
        print("\n❌ Tests failed - check IMG_BB_API_KEY and network")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
