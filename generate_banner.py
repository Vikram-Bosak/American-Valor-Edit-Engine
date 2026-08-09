from PIL import Image, ImageDraw, ImageFont
import os

width = 1070
height = 90

# Rich Navy Blue background
img = Image.new('RGBA', (width, height), (26, 47, 76, 255))
draw = ImageDraw.Draw(img)

# Golden border at the bottom
draw.line([(0, height-3), (width, height-3)], fill=(255, 215, 0, 255), width=3)

# Fonts configuration
font_bold = 'C:/Windows/Fonts/arialbd.ttf'
if not os.path.exists(font_bold):
    font_bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

try:
    f_title = ImageFont.truetype(font_bold, 45)
    f_side = ImageFont.truetype(font_bold, 30)
except IOError:
    f_title = f_side = ImageFont.load_default()

# 1. Draw Center Text "AMERICAN VALOR"
title_text = "AMERICAN VALOR"
try:
    text_w = int(draw.textlength(title_text, font=f_title))
except AttributeError:
    bbox = draw.textbbox((0, 0), title_text, font=f_title)
    text_w = bbox[2] - bbox[0]
    
title_x = (width - text_w) // 2
title_y = (height - 45) // 2 - 5

# Draw drop shadow for 3D effect
shadow_color = (0, 0, 0, 220)
for offset in [(2,2), (-2,-2), (2,-2), (-2,2), (0,2), (2,0), (-2,0), (0,-2)]:
    draw.text((title_x + offset[0], title_y + offset[1]), title_text, fill=shadow_color, font=f_title)

# Draw main title in metallic gold
draw.text((title_x, title_y), title_text, fill=(255, 215, 0, 255), font=f_title)

# 2. Draw Left Logo (Gold badge with star)
badge_x = 35
badge_y = 15
badge_size = 55
# Outer gold circle
draw.ellipse([badge_x, badge_y, badge_x + badge_size, badge_y + badge_size], fill=(255, 215, 0, 255), outline=(255, 255, 255, 255), width=2)
# Text "AV" inside badge
draw.text((badge_x + 9, badge_y + 11), "AV", fill=(26, 47, 76, 255), font=f_side)

# 3. Draw Right Badge (Gold badge with 'US')
r_badge_x = width - badge_size - 35
# Outer gold circle
draw.ellipse([r_badge_x, badge_y, r_badge_x + badge_size, badge_y + badge_size], fill=(255, 215, 0, 255), outline=(255, 255, 255, 255), width=2)
# Text "US" inside badge
draw.text((r_badge_x + 9, badge_y + 11), "US", fill=(26, 47, 76, 255), font=f_side)

# Save to assets/top_banner_extracted.png
output_dir = 'C:/Users/admin/.gemini/antigravity-ide/scratch/usa_military_army_agent_1/assets'
os.makedirs(output_dir, exist_ok=True)
img.save(os.path.join(output_dir, 'top_banner_extracted.png'), 'PNG')
print("New banner 'top_banner_extracted.png' generated successfully!")
