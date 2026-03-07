import sys
from PIL import Image

def apply_white_corners(target_path, sample_path, out_path):
    # Open the generated image (target) and the sample image
    target = Image.open(target_path).convert("RGB")
    sample = Image.open(sample_path).convert("RGB")
    
    # Resize target to match sample exactly
    target = target.resize(sample.size, Image.Resampling.LANCZOS)
    
    # Get pixel data
    target_pixels = target.load()
    sample_pixels = sample.load()
    
    # Apply the white corners from the sample onto the target
    for x in range(target.width):
        for y in range(target.height):
            # If the sample pixel is effectively white (the corner masking)
            s_r, s_g, s_b = sample_pixels[x, y]
            if s_r > 240 and s_g > 240 and s_b > 240:
                target_pixels[x, y] = (255, 255, 255) # Force white corner
                
    # Save the result
    target.save(out_path)
    print(f"Successfully created {out_path} matching the sample corners exactly.")

if __name__ == "__main__":
    apply_white_corners(sys.argv[1], sys.argv[2], sys.argv[3])
