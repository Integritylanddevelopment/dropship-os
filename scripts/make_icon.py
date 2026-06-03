from PIL import Image, ImageDraw, ImageFont
import math

size = 512
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background — deep navy rounded square
def rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0+radius, y0, x1-radius, y1], fill=fill)
    draw.rectangle([x0, y0+radius, x1, y1-radius], fill=fill)
    draw.ellipse([x0, y0, x0+radius*2, y0+radius*2], fill=fill)
    draw.ellipse([x1-radius*2, y0, x1, y0+radius*2], fill=fill)
    draw.ellipse([x0, y1-radius*2, x0+radius*2, y1], fill=fill)
    draw.ellipse([x1-radius*2, y1-radius*2, x1, y1], fill=fill)

rounded_rect(draw, [0, 0, size, size], 80, (15, 20, 40, 255))

# Ship hull — bold white/gold shape centered
hull_color = (255, 200, 50, 255)       # gold
accent_color = (255, 255, 255, 255)    # white
blue_accent = (80, 160, 255, 255)      # electric blue

# Hull body (trapezoid)
hull = [(100, 310), (412, 310), (370, 390), (142, 390)]
draw.polygon(hull, fill=hull_color)

# Hull deck line
draw.rectangle([110, 295, 402, 315], fill=accent_color)

# Cabin / superstructure
cabin = [(180, 200), (332, 200), (332, 295), (180, 295)]
draw.rectangle(cabin, fill=accent_color)

# Cabin windows — blue circles
for cx in [210, 256, 302]:
    draw.ellipse([cx-18, 228-18, cx+18, 228+18], fill=blue_accent)

# Funnel / mast
draw.rectangle([240, 130, 272, 202], fill=hull_color)
draw.ellipse([226, 118, 286, 148], fill=hull_color)

# AI spark — small circuit lines top right
spark_x, spark_y = 370, 130
for angle, length in [(0,22),(60,18),(120,22),(180,18),(240,22),(300,18)]:
    rad = math.radians(angle)
    ex = int(spark_x + math.cos(rad)*length)
    ey = int(spark_y + math.sin(rad)*length)
    draw.line([(spark_x, spark_y),(ex,ey)], fill=blue_accent, width=4)
draw.ellipse([spark_x-10, spark_y-10, spark_x+10, spark_y+10], fill=blue_accent)

# Wake lines under hull
for i, y in enumerate([408, 422, 436]):
    margin = i * 20
    draw.arc([100+margin, y-12, 412-margin, y+12], 0, 180, fill=accent_color, width=3)

# Save
out = r"C:\Users\integ\Documents\Claude\Projects\Drop shipping\shipstack_icon.png"
img.save(out)
print(f"Saved: {out}")
