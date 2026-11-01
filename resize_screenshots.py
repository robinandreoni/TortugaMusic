import os
from PIL import Image

output_dir = r"C:\Users\robin\Desktop\cyber\TortugaMusic\PlayStore_Assets"
os.makedirs(output_dir, exist_ok=True)

images = {
    "Screenshot_1_Home.png": r"C:\Users\robin\.gemini\antigravity-ide\brain\786a0e70-5de2-45a1-8b75-8fd94e07537b\screenshot_home_1786561240219.png",
    "Screenshot_2_Player.png": r"C:\Users\robin\.gemini\antigravity-ide\brain\786a0e70-5de2-45a1-8b75-8fd94e07537b\screenshot_player_1786561352250.png",
    "Screenshot_3_Video.png": r"C:\Users\robin\.gemini\antigravity-ide\brain\786a0e70-5de2-45a1-8b75-8fd94e07537b\screenshot_video_1786561369681.png",
    "Screenshot_4_Search.png": r"C:\Users\robin\.gemini\antigravity-ide\brain\786a0e70-5de2-45a1-8b75-8fd94e07537b\screenshot_search_1786561388470.png"
}

target_w, target_h = 1080, 1920

for name, src in images.items():
    if os.path.exists(src):
        img = Image.open(src)
        # We need to fill 1080x1920 exactly
        ratio = max(target_w / img.width, target_h / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Center crop
        left = (new_w - target_w) / 2
        top = (new_h - target_h) / 2
        img = img.crop((left, top, left + target_w, top + target_h))
        
        img = img.convert('RGB')
        img.save(os.path.join(output_dir, name))
        print(f"Processed {name}")
    else:
        print(f"File not found: {src}")
