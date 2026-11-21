#!/usr/bin/env python3
"""
Denoise and enhance an existing profile picture using Gemini's image-to-image modality.
Uses GEMINI_KEY from .env file via standard client.models.generate_content endpoint.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from PIL import Image

# Load .env from repo root
REPO_ROOT = Path(__file__).parent.parent
load_dotenv(REPO_ROOT / ".env")

# Paths
PHYSICS_IMAGES = "/Users/vkapoor/python_workspace/physics_book/src/physics_book/papers/electrodynamics/figures/"
OUTPUT_DIR =  "/Users/vkapoor/python_workspace/physics_book/src/physics_book/papers/electrodynamics/figures/enhanced_images/"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Initialize Gemini Client
api_key = os.getenv("GEMINI_KEY")
if not api_key:
    raise ValueError("GEMINI_KEY not found in environment variables. Check your .env file.")

client = genai.Client(api_key=api_key)

def enhance_image(image_path: Path):
    if not image_path.exists():
        print(f"Error: Image not found at {image_path}")
        return

    print(f"Loading original image: {image_path.name}...")
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"Failed to open image: {e}")
        return

    # This prompt tells the model to keep the subject exactly the same but fix quality/noise
    enhancement_prompt = ("This is a hand drawn image for a lecutre on electrodynamics, we need to create book quality image from it, that look professional while preserving the actual content of the image")
    #enhancement_prompt = (
    #    "This image is a compressed screenshot. Modify and enhance this exact image: "
    #    "Remove all pixelation, digital noise, grain, and blocky compression artifacts. "
    #    "Smooth out the textures, clean the background, and sharpen lines to make it look "
    #    "like a high-quality, professional, studio-shot profile picture. Maintain the exact "
    #    "same person , facial features, pose, clothing, and composition. Do not generate a new scene."
    #)

    print("Sending image and enhancement prompt to Gemini (gemini-3.1-flash-image)...")
    
    # CRITICAL FIX: Pass BOTH the original image and the text prompt into generate_content
    generation_response = client.models.generate_content(
        model="gemini-3.1-flash-image",
        contents=[img, enhancement_prompt]
    )

    output_filename = f"{image_path.stem}_enhanced.png"
    output_path = OUTPUT_DIR / output_filename

    # Extract the resulting edited image bytes from the inline_data parts
    image_saved = False
    for part in generation_response.parts:
        if part.inline_data is not None:
            generated_img = part.as_image()
            generated_img.save(output_path)
            print(f"Success! Denoised and enhanced image saved to: {output_path}")
            image_saved = True
            break

    if not image_saved:
        print("Error: The API did not return an image part in its response payload.")
        if generation_response.text:
            print(f"API Text Output: {generation_response.text}")

if __name__ == "__main__":
    
    for image in PHYSICS_IMAGES:
      enhance_image(image)
