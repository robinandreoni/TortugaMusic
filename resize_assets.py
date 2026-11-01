from PIL import Image
import os

feature_src = r"C:\Users\robin\.gemini\antigravity-ide\brain\786a0e70-5de2-45a1-8b75-8fd94e07537b\feature_graphic_1786560763743.png"
icon_src = r"C:\Users\robin\.gemini\antigravity-ide\brain\786a0e70-5de2-45a1-8b75-8fd94e07537b\playstore_icon_1786560785320.png"
output_dir = r"C:\Users\robin\.gemini\antigravity-ide\brain\786a0e70-5de2-45a1-8b75-8fd94e07537b"

# Feature Graphic -> 1024x500
if os.path.exists(feature_src):
    img = Image.open(feature_src)
    # resize to width 1024, keeping aspect ratio, then crop center to 500
    ratio = 1024.0 / img.width
    new_h = int(img.height * ratio)
    if new_h < 500:
        # scale based on height instead
        ratio = 500.0 / img.height
        new_w = int(img.width * ratio)
        img = img.resize((new_w, 500), Image.Resampling.LANCZOS)
        # crop horizontally
        left = (new_w - 1024) / 2
        img = img.crop((left, 0, left + 1024, 500))
    else:
        img = img.resize((1024, new_h), Image.Resampling.LANCZOS)
        # crop vertically
        top = (new_h - 500) / 2
        img = img.crop((0, top, 1024, top + 500))
    
    img = img.convert('RGB')
    img.save(os.path.join(output_dir, "Immagine_Primo_Piano_1024x500.png"))
    print("Feature graphic generated successfully.")

# Icon -> 512x512
if os.path.exists(icon_src):
    img = Image.open(icon_src)
    img = img.resize((512, 512), Image.Resampling.LANCZOS)
    img = img.convert('RGBA')
    img.save(os.path.join(output_dir, "Icona_App_512x512.png"))
    print("Icon generated successfully.")
