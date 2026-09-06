# Bug Found: Dead Async Function Definition in services.py

## Location
File: `backend/services.py`, lines 330-333

## Bug Description
In the `generate_image()` method (which is a synchronous function), there's a nested async function `upload_to_imgbb()` defined on lines 330-333 that is **never called**. This is dead code that serves no purpose.

## Code in Question
```python
def generate_image(self, prompt: str) -> Optional[str]:
    # ... code ...
    image_url = image_response.data[0].url
    
    # Download and upload to imgbb (as n8n does)
    async def upload_to_imgbb(image_data: bytes) -> Optional[str]:
        # Note: In production, you'd want proper async handling
        # For now, we'll use the direct DALL-E URL
        return image_url
    
    return image_url  # <-- The async function is never called!
```

## Why This is a Bug

1. **Dead Code**: The `upload_to_imgbb` async function is defined but never invoked
2. **Misleading Comment**: The comment says "Download and upload to imgbb (as n8n does)" but the code doesn't actually do this - it just returns the DALL-E URL directly
3. **Inconsistent with n8n Workflow**: The original n8n workflow has an actual "Upload Image (imgbb)" step that uploads images to imgbb.com, but this implementation skips that step entirely
4. **Async/Sync Confusion**: Defining an async function inside a sync function without calling it creates confusion about the intended execution flow

## Impact

According to the n8n workflow:
- The original workflow uploads generated images to imgbb.com for permanent hosting
- This implementation only returns the temporary DALL-E URL which may expire
- Images sent to Telegram may become unavailable if DALL-E URLs expire

## Suggested Fix

Either:
1. **Remove the dead code** and update the comment to be accurate, OR
2. **Implement the actual imgbb upload functionality** by:
   - Making `generate_image()` async
   - Actually calling `await upload_to_imgbb()` with the downloaded image data
   - Using the imgbb API to upload and get a permanent URL

## Business Rule Violation

This violates constraint #4 from the task requirements:
> "Match the original's error handling behavior" 

The n8n workflow explicitly includes an imgbb upload step, but this implementation bypasses it, potentially causing broken images in Telegram posts.
