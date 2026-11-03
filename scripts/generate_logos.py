import os
from pathlib import Path

# Enable headless Qt rendering on Linux
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PIL import Image
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

OUTPUT_DIR = Path("assets/logo")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. ICON SVG (Standalone Square App Icon / Mark)
ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0B0F19"/>
      <stop offset="50%" stop-color="#0F172A"/>
      <stop offset="100%" stop-color="#020617"/>
    </linearGradient>

    <!-- Deep Tech Blue Spine Gradient -->
    <linearGradient id="spineGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#3B82F6"/>
      <stop offset="50%" stop-color="#2563EB"/>
      <stop offset="100%" stop-color="#1D4ED8"/>
    </linearGradient>

    <!-- Outer Geometric D Arc Gradient -->
    <linearGradient id="arcGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60A5FA"/>
      <stop offset="40%" stop-color="#3B82F6"/>
      <stop offset="80%" stop-color="#1E40AF"/>
      <stop offset="100%" stop-color="#1E3A8A"/>
    </linearGradient>

    <!-- Ascending Alpha Delta Gradient (Cyan to Emerald) -->
    <linearGradient id="alphaGrad" x1="0%" y1="100%" x2="50%" y2="0%">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="40%" stop-color="#06B6D4"/>
      <stop offset="80%" stop-color="#10B981"/>
      <stop offset="100%" stop-color="#34D399"/>
    </linearGradient>

    <!-- Accent Glow Gradient -->
    <linearGradient id="glowGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#10B981" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#06B6D4" stop-opacity="0.2"/>
    </linearGradient>

    <!-- Drop Shadows & Glow -->
    <filter id="alphaGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>

    <filter id="cardShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="16" stdDeviation="24" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
  </defs>

  <!-- Squircle Canvas Card -->
  <rect x="24" y="24" width="464" height="464" rx="108" ry="108" fill="url(#bgGrad)" stroke="#1E293B" stroke-width="3" filter="url(#cardShadow)"/>

  <!-- Subtle High-Frequency Trading Grid Background Lines -->
  <g opacity="0.07" stroke="#94A3B8" stroke-width="1.5">
    <line x1="80" y1="170" x2="432" y2="170" stroke-dasharray="4,8"/>
    <line x1="80" y1="256" x2="432" y2="256" stroke-dasharray="4,8"/>
    <line x1="80" y1="342" x2="432" y2="342" stroke-dasharray="4,8"/>
    <line x1="170" y1="80" x2="170" y2="432" stroke-dasharray="4,8"/>
    <line x1="256" y1="80" x2="256" y2="432" stroke-dasharray="4,8"/>
    <line x1="342" y1="80" x2="342" y2="432" stroke-dasharray="4,8"/>
  </g>

  <!-- OUTER GEOMETRIC 'D' MONOGRAM -->
  <!-- Left Pillar / Spine -->
  <path d="M 124 132 C 124 121 133 112 144 112 L 176 112 C 187 112 196 121 196 132 L 196 380 C 196 391 187 400 176 400 L 144 400 C 133 400 124 391 124 380 Z" 
        fill="url(#spineGrad)"/>

  <!-- Outer Faceted Geometric Arc -->
  <path d="M 196 112 L 290 112 C 342 112 388 154 388 208 C 388 238 374 266 352 284 L 388 322 L 344 366 L 302 324 L 250 324 L 250 400 L 196 400 Z" 
        fill="url(#arcGrad)" opacity="0.95"/>

  <!-- Inner Counter Cutout (giving the D its negative space) -->
  <path d="M 196 168 L 278 168 C 308 168 332 192 332 222 C 332 252 308 276 278 276 L 196 276 Z" 
        fill="#0B0F19"/>

  <!-- ASCENDING ALPHA DELTA / FINANCIAL ALGORITHMIC CHEVRON (High Profit Vector) -->
  <g filter="url(#alphaGlow)">
    <!-- Primary Ascending Chevron Arrowhead -->
    <path d="M 284 140 L 404 260 L 362 302 L 284 224 L 206 302 L 164 260 Z" 
          fill="url(#alphaGrad)"/>
    
    <!-- Secondary Precision Dynamic Candlestick Pin -->
    <rect x="278" y="104" width="12" height="42" rx="6" fill="#34D399"/>
  </g>

  <!-- Triple-Barrier Horizon Indicators (Quantitative Markers) -->
  <circle cx="160" cy="148" r="5" fill="#60A5FA"/>
  <circle cx="160" cy="256" r="5" fill="#38BDF8"/>
  <circle cx="160" cy="364" r="5" fill="#34D399"/>
</svg>
"""

# 2. FULL HORIZONTAL LOGO (For Header, Splash, Reports, Documentation)
HORIZONTAL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" width="1200" height="320">
  <defs>
    <linearGradient id="hBgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0B0F19"/>
      <stop offset="100%" stop-color="#020617"/>
    </linearGradient>

    <linearGradient id="hSpineGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#3B82F6"/>
      <stop offset="100%" stop-color="#1D4ED8"/>
    </linearGradient>

    <linearGradient id="hArcGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60A5FA"/>
      <stop offset="50%" stop-color="#3B82F6"/>
      <stop offset="100%" stop-color="#1E3A8A"/>
    </linearGradient>

    <linearGradient id="hAlphaGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="50%" stop-color="#06B6D4"/>
      <stop offset="100%" stop-color="#10B981"/>
    </linearGradient>

    <linearGradient id="fxGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#10B981"/>
      <stop offset="100%" stop-color="#34D399"/>
    </linearGradient>

    <filter id="hGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- LOGOMARK (X: 40, Y: 40, 240x240) -->
  <g transform="translate(40, 40)">
    <!-- Squircle Card -->
    <rect x="0" y="0" width="240" height="240" rx="56" ry="56" fill="url(#hBgGrad)" stroke="#1E293B" stroke-width="2"/>
    
    <!-- Grid -->
    <g opacity="0.08" stroke="#94A3B8" stroke-width="1">
      <line x1="30" y1="120" x2="210" y2="120" stroke-dasharray="3,5"/>
      <line x1="120" y1="30" x2="120" y2="210" stroke-dasharray="3,5"/>
    </g>

    <!-- Scaled Mark -->
    <g transform="translate(18, 18) scale(0.4)">
      <!-- Left Spine -->
      <path d="M 124 132 C 124 121 133 112 144 112 L 176 112 C 187 112 196 121 196 132 L 196 380 C 196 391 187 400 176 400 L 144 400 C 133 400 124 391 124 380 Z" fill="url(#hSpineGrad)"/>

      <!-- Outer Arc -->
      <path d="M 196 112 L 290 112 C 342 112 388 154 388 208 C 388 238 374 266 352 284 L 388 322 L 344 366 L 302 324 L 250 324 L 250 400 L 196 400 Z" fill="url(#hArcGrad)"/>

      <!-- Inner Counter -->
      <path d="M 196 168 L 278 168 C 308 168 332 192 332 222 C 332 252 308 276 278 276 L 196 276 Z" fill="#0B0F19"/>

      <!-- Ascending Chevron -->
      <g filter="url(#hGlow)">
        <path d="M 284 140 L 404 260 L 362 302 L 284 224 L 206 302 L 164 260 Z" fill="url(#hAlphaGrad)"/>
        <rect x="278" y="104" width="12" height="42" rx="6" fill="#34D399"/>
      </g>
    </g>
  </g>

  <!-- TYPOGRAPHY / WORDMARK -->
  <g transform="translate(320, 160)">
    <!-- "DARE" in Sharp Heavy Technical Sans -->
    <text x="0" y="10" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" 
          font-size="112" font-weight="900" letter-spacing="4" fill="#0F172A">DARE</text>

    <!-- "FX" in High-Alpha Emerald Accent -->
    <text x="328" y="10" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" 
          font-size="112" font-weight="900" letter-spacing="4" fill="url(#fxGrad)">FX</text>

    <!-- Subtitle / Positioning Tagline -->
    <text x="4" y="68" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" 
          font-size="22" font-weight="700" letter-spacing="9" fill="#64748B">QUANTITATIVE AI TRADING STATION</text>

    <!-- Precision Execution Accent Badges -->
    <g transform="translate(510, -58)">
      <rect x="0" y="0" width="116" height="30" rx="15" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1.5"/>
      <circle cx="16" cy="15" r="5" fill="#10B981"/>
      <text x="28" y="21" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" font-size="12" font-weight="800" fill="#047857" letter-spacing="1">INSTITUTIONAL</text>
    </g>
  </g>
</svg>
"""

# 3. LIGHT THEME FULL LOGO (Optimized for #F8FAFC UI Header)
LIGHT_HEADER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 88" width="480" height="88">
  <defs>
    <linearGradient id="lhSpine" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#2563EB"/>
      <stop offset="100%" stop-color="#1D4ED8"/>
    </linearGradient>
    <linearGradient id="lhAlpha" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0284C7"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>
    <linearGradient id="lhFx" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#059669"/>
      <stop offset="100%" stop-color="#10B981"/>
    </linearGradient>
  </defs>

  <!-- Icon (X: 4, Y: 8, 72x72) -->
  <g transform="translate(4, 8)">
    <rect x="0" y="0" width="72" height="72" rx="18" ry="18" fill="#0F172A"/>
    <g transform="translate(6, 6) scale(0.117)">
      <path d="M 124 132 C 124 121 133 112 144 112 L 176 112 C 187 112 196 121 196 132 L 196 380 C 196 391 187 400 176 400 L 144 400 C 133 400 124 391 124 380 Z" fill="url(#lhSpine)"/>
      <path d="M 196 112 L 290 112 C 342 112 388 154 388 208 C 388 238 374 266 352 284 L 388 322 L 344 366 L 302 324 L 250 324 L 250 400 L 196 400 Z" fill="#3B82F6"/>
      <path d="M 196 168 L 278 168 C 308 168 332 192 332 222 C 332 252 308 276 278 276 L 196 276 Z" fill="#0F172A"/>
      <path d="M 284 140 L 404 260 L 362 302 L 284 224 L 206 302 L 164 260 Z" fill="url(#lhAlpha)"/>
      <rect x="278" y="104" width="12" height="42" rx="6" fill="#34D399"/>
    </g>
  </g>

  <!-- Text -->
  <g transform="translate(92, 45)">
    <text x="0" y="0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="34" font-weight="900" letter-spacing="1.5" fill="#0F172A">DARE</text>
    <text x="96" y="0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="34" font-weight="900" letter-spacing="1.5" fill="url(#lhFx)">FX</text>
    <text x="1" y="21" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" font-weight="700" letter-spacing="3" fill="#64748B">QUANTITATIVE AI TRADING</text>
  </g>
</svg>
"""

# 4. DARK THEME FULL LOGO (For Dark Terminal / Presentations / GitHub Header)
DARK_HORIZONTAL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" width="1200" height="320">
  <defs>
    <linearGradient id="dhBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#020617"/>
      <stop offset="100%" stop-color="#0B0F19"/>
    </linearGradient>
    <linearGradient id="dhSpine" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#3B82F6"/>
      <stop offset="100%" stop-color="#1D4ED8"/>
    </linearGradient>
    <linearGradient id="dhArc" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60A5FA"/>
      <stop offset="100%" stop-color="#1E3A8A"/>
    </linearGradient>
    <linearGradient id="dhAlpha" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="50%" stop-color="#06B6D4"/>
      <stop offset="100%" stop-color="#10B981"/>
    </linearGradient>
    <linearGradient id="dhFx" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#10B981"/>
      <stop offset="100%" stop-color="#34D399"/>
    </linearGradient>
    <filter id="dhGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <rect width="1200" height="320" rx="24" fill="url(#dhBg)"/>

  <!-- Logomark -->
  <g transform="translate(48, 40)">
    <rect x="0" y="0" width="240" height="240" rx="56" ry="56" fill="#0B0F19" stroke="#1E293B" stroke-width="2"/>
    <g transform="translate(18, 18) scale(0.4)">
      <path d="M 124 132 C 124 121 133 112 144 112 L 176 112 C 187 112 196 121 196 132 L 196 380 C 196 391 187 400 176 400 L 144 400 C 133 400 124 391 124 380 Z" fill="url(#dhSpine)"/>
      <path d="M 196 112 L 290 112 C 342 112 388 154 388 208 C 388 238 374 266 352 284 L 388 322 L 344 366 L 302 324 L 250 324 L 250 400 L 196 400 Z" fill="url(#dhArc)"/>
      <path d="M 196 168 L 278 168 C 308 168 332 192 332 222 C 332 252 308 276 278 276 L 196 276 Z" fill="#0B0F19"/>
      <g filter="url(#dhGlow)">
        <path d="M 284 140 L 404 260 L 362 302 L 284 224 L 206 302 L 164 260 Z" fill="url(#dhAlpha)"/>
        <rect x="278" y="104" width="12" height="42" rx="6" fill="#34D399"/>
      </g>
    </g>
  </g>

  <!-- Typography -->
  <g transform="translate(328, 160)">
    <text x="0" y="10" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="112" font-weight="900" letter-spacing="4" fill="#F8FAFC">DARE</text>
    <text x="328" y="10" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="112" font-weight="900" letter-spacing="4" fill="url(#dhFx)">FX</text>
    <text x="4" y="68" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="22" font-weight="700" letter-spacing="9" fill="#94A3B8">QUANTITATIVE AI TRADING STATION</text>
  </g>
</svg>
"""


def render_svg_to_image(svg_content: str, width: int, height: int) -> QImage:
    """Render SVG string to high-quality QImage with antialiasing."""
    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    return image


def main():
    app = QApplication.instance() or QApplication([])

    # 1. Save SVGs
    icon_svg_path = OUTPUT_DIR / "darefx-icon.svg"
    icon_svg_path.write_text(ICON_SVG, encoding="utf-8")
    print(f"Saved: {icon_svg_path}")

    h_svg_path = OUTPUT_DIR / "darefx-logo-horizontal.svg"
    h_svg_path.write_text(HORIZONTAL_SVG, encoding="utf-8")
    print(f"Saved: {h_svg_path}")

    light_svg_path = OUTPUT_DIR / "darefx-logo-light.svg"
    light_svg_path.write_text(LIGHT_HEADER_SVG, encoding="utf-8")
    print(f"Saved: {light_svg_path}")

    dark_svg_path = OUTPUT_DIR / "darefx-logo-dark.svg"
    dark_svg_path.write_text(DARK_HORIZONTAL_SVG, encoding="utf-8")
    print(f"Saved: {dark_svg_path}")

    # 2. Render PNGs
    # Icon 512x512
    img_512 = render_svg_to_image(ICON_SVG, 512, 512)
    img_512.save(str(OUTPUT_DIR / "darefx-icon-512.png"))

    # Icon 256x256
    img_256 = render_svg_to_image(ICON_SVG, 256, 256)
    img_256.save(str(OUTPUT_DIR / "darefx-icon-256.png"))

    # Icon 128x128
    img_128 = render_svg_to_image(ICON_SVG, 128, 128)
    img_128.save(str(OUTPUT_DIR / "darefx-icon-128.png"))

    # Icon 64x64
    img_64 = render_svg_to_image(ICON_SVG, 64, 64)
    img_64.save(str(OUTPUT_DIR / "darefx-icon-64.png"))

    # Icon 32x32
    img_32 = render_svg_to_image(ICON_SVG, 32, 32)
    img_32.save(str(OUTPUT_DIR / "darefx-icon-32.png"))

    # Standard darefx-icon.png (256x256)
    img_256.save(str(OUTPUT_DIR / "darefx-icon.png"))
    print("Saved icon PNGs (512, 256, 128, 64, 32)")

    # Full Horizontal Logo PNGs (1200x320 & 600x160)
    h_img_1200 = render_svg_to_image(HORIZONTAL_SVG, 1200, 320)
    h_img_1200.save(str(OUTPUT_DIR / "darefx-logo-horizontal.png"))

    # Light Header PNG (480x88)
    light_img = render_svg_to_image(LIGHT_HEADER_SVG, 480, 88)
    light_img.save(str(OUTPUT_DIR / "darefx-logo-header.png"))

    # Dark Logo PNG
    dark_img = render_svg_to_image(DARK_HORIZONTAL_SVG, 1200, 320)
    dark_img.save(str(OUTPUT_DIR / "darefx-logo-dark.png"))
    print("Saved horizontal and header PNGs")

    # 3. Create Windows Multi-Resolution .ICO file for Desktop Shortcut and Window Icon
    # Windows .ico packages sizes: 16, 24, 32, 48, 64, 128, 256
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    pil_images = []
    for sz in ico_sizes:
        qimg = render_svg_to_image(ICON_SVG, sz, sz)
        tmp_png = OUTPUT_DIR / f"_tmp_{sz}.png"
        qimg.save(str(tmp_png))
        pil_im = Image.open(tmp_png)
        pil_images.append(pil_im)

    ico_path = OUTPUT_DIR / "darefx.ico"
    # Save as multi-resolution ICO
    pil_images[-1].save(
        str(ico_path),
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=pil_images[:-1],
    )
    print(f"Saved Windows multi-resolution icon: {ico_path}")

    # Clean up temp files
    for sz in ico_sizes:
        tmp_png = OUTPUT_DIR / f"_tmp_{sz}.png"
        if tmp_png.exists():
            tmp_png.unlink()

    print("All DareFX brand assets successfully generated!")


if __name__ == "__main__":
    main()
