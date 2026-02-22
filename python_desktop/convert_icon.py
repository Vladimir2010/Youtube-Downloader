from PIL import Image
import os

img_path = 'app_icon.png'
ico_path = 'app_icon.ico'

if os.path.exists(img_path):
    img = Image.open(img_path)
    img.save(ico_path, format='ICO', sizes=[(256, 256)])
    print(f"Created {ico_path}")
else:
    print(f"Image {img_path} not found")
