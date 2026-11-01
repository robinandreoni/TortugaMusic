from PIL import Image
import os
import shutil

base_dir = r"c:\Users\robin\Desktop\cyber\TortugaMusic"
icon_src = os.path.join(base_dir, "iconagenerale.jpeg")
bg_src = os.path.join(base_dir, "iconasfondo.jpeg")

res_dir = os.path.join(base_dir, "android", "app", "src", "main", "res")
static_dir = os.path.join(base_dir, "android", "app", "src", "main", "python", "static")

os.makedirs(static_dir, exist_ok=True)

# 1. Copia asset nel frontend static
shutil.copy2(icon_src, os.path.join(static_dir, "icona_app.jpg"))
shutil.copy2(bg_src, os.path.join(static_dir, "sfondo_app.jpg"))
print("Assets copiati in static/")

# 2. Genera icone Android mipmap
icon_sizes = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

if os.path.exists(icon_src):
    img = Image.open(icon_src).convert("RGBA")
    
    # Crea versione per ogni densità
    for folder, size in icon_sizes.items():
        out_folder = os.path.join(res_dir, folder)
        os.makedirs(out_folder, exist_ok=True)
        
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(out_folder, "ic_launcher.png"), "PNG")
        resized.save(os.path.join(out_folder, "ic_launcher_round.png"), "PNG")
        print(f"Generata icona per {folder}: {size}x{size}")
        
    # Drawable ic_launcher
    drawable_dir = os.path.join(res_dir, "drawable")
    os.makedirs(drawable_dir, exist_ok=True)
    img_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
    img_512.save(os.path.join(drawable_dir, "ic_launcher.png"), "PNG")
    print("Generata icona 512x512 in drawable/ic_launcher.png")

print("Completato con successo!")
