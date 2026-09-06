---
name: Image Upload Bug
about: Dead code in generate_image method causes missing imgbb upload
title: 'BUG: Dead async function upload_to_imgbb never called - images may expire'
labels: bug, critical
assignees: ''

---

## Bug Summary
Dead async function `upload_to_imgbb` defined but never called in the `generate_image()` method, causing images to use temporary DALL-E URLs instead of permanent imgbb hosting.

## Location
- **File**: `backend/services.py`
- **Lines**: 330-333
- **Method**: `CategorizationService.generate_image()`

## Problem Code
```python
def generate_image(self, prompt: str) -> Optional[str]:
    # ... generates image with DALL-E ...
    image_url = image_response.data[0].url
    
    # Download and upload to imgbb (as n8n does)
    async def upload_to_imgbb(image_data: bytes) -> Optional[str]:
        # Note: In production, you'd want proper async handling
        # For now, we'll use the direct DALL-E URL
        return image_url  # <-- This function is NEVER CALLED!
    
    return image_url  # Returns temporary DALL-E URL directly
```

## Expected Behavior (from n8n workflow)
1. Generate image with DALL-E
2. Download the image data
3. Upload to imgbb.com via HTTP request
4. Use the permanent imgbb URL for Telegram posts

## Actual Behavior
- The `upload_to_imgbb` async function is defined but never invoked
- Method returns temporary DALL-E URL directly
- Images may become unavailable when DALL-E URLs expire

## Impact on Users
- **Critical**: Telegram posts may have broken images after DALL-E URLs expire
- Does not match original n8n workflow behavior
- Violates project requirement to "Match the original's error handling behavior"

## Suggested Fix Options

### Option 1: Remove dead code (quick fix)
```python
def generate_image(self, prompt: str) -> Optional[str]:
    if not self.client:
        logger.warning("No OpenAI client for image generation")
        return None
    
    try:
        image_response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return image_response.data[0].url  # Document that this is temporary
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None
```

### Option 2: Implement proper imgbb upload (recommended)
```python
async def generate_image(self, prompt: str) -> Optional[str]:
    if not self.client:
        logger.warning("No OpenAI client for image generation")
        return None
    
    try:
        # Generate with DALL-E
        image_response = self.client.images.generate(...)
        dalle_url = image_response.data[0].url
        
        # Download image
        async with httpx.AsyncClient() as client:
            img_data = await client.get(dalle_url)
            
        # Upload to imgbb
        imgbb_url = await self._upload_to_imgbb(img_data.content)
        return imgbb_url
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

async def _upload_to_imgbb(self, image_data: bytes) -> Optional[str]:
    # Implement actual imgbb API upload
    pass
```

## Related Files
- `backend/services.py` - Contains the bug
- `.github/workflows/ci-cd.yml` - Should test image upload functionality
- `backend/config.py` - May need IMGBB_API_KEY setting

## Testing Checklist
- [ ] Verify DALL-E image generation works
- [ ] Test imgbb upload with real API key
- [ ] Confirm Telegram posts have working image URLs
- [ ] Add integration test for full image pipeline
