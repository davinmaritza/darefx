"""Convert the AI-generated logo mark to Windows .ico and transparent PNG icon."""
from pathlib import Path
from PIL import Image

def main():
    src_path = Path("assets/logo/darefx-ai-mark.jpg")
    if not src_path.exists():
        print("Source not found")
        return

    im = Image.open(src_path).convert("RGBA")
    w, h = im.size

    # Crop to square center if not already square
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    cropped = im.crop((left, top, left + min_dim, top + min_dim))

    # Resize to standard sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_images = [cropped.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]

    # Save darefx-app.png (256x256)
    cropped.resize((256, 256), Image.Resampling.LANCZOS).save("assets/logo/darefx-app.png")
    cropped.resize((512, 512), Image.Resampling.LANCZOS).save("assets/logo/darefx-app-512.png")

    # Save as darefx-app.ico
    ico_path = Path("assets/logo/darefx-app.ico")
    ico_images[-1].save(
        str(ico_path),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=ico_images[:-1],
    )
    print(f"Saved: {ico_path} and darefx-app.png")

if __name__ == "__main__":
    main()
