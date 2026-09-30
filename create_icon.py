"""
Generador de ícono institucional .ico para el ejecutable de Windows.
"""

from PIL import Image, ImageDraw

def create_shield_icon():
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []

    for size in sizes:
        w, h = size
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Coordenadas de escudo
        margin = int(w * 0.08)
        top = margin
        left = margin
        right = w - margin
        bottom = h - margin
        mid_x = w // 2

        shield_points = [
            (mid_x, top),
            (right, int(top + (bottom - top) * 0.2)),
            (right, int(top + (bottom - top) * 0.65)),
            (mid_x, bottom),
            (left, int(top + (bottom - top) * 0.65)),
            (left, int(top + (bottom - top) * 0.2)),
        ]

        # Fondo del escudo en azul marino / zafiro
        draw.polygon(shield_points, fill=(30, 64, 175, 255), outline=(56, 189, 248, 255), width=max(1, int(w * 0.04)))

        # Símbolo central (Sol / Cruz / Guardia)
        inner_margin = int(w * 0.25)
        draw.ellipse([inner_margin, inner_margin, w - inner_margin, h - inner_margin], fill=(245, 158, 11, 255), outline=(255, 255, 255, 255), width=max(1, int(w * 0.02)))
        
        images.append(img)

    images[0].save("app_icon.ico", format="ICO", sizes=[(im.width, im.height) for im in images])
    print("[+] app_icon.ico generado correctamente.")

if __name__ == "__main__":
    create_shield_icon()
