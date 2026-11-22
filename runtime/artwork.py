"""Original SVG concept illustrations, deliberately labelled as local concept art in the UI."""
import math
import random


def artwork(variant=0):
    variant = int(variant) % 6
    rng = random.Random(72 + variant)
    palette = [("#0a1520", "#34444b", "#d09767"), ("#071d26", "#1b6570", "#ec9e6c"),
               ("#152a2c", "#64887a", "#d8dfb5"), ("#181624", "#625467", "#dab698"),
               ("#1e2026", "#77746a", "#edce98"), ("#1b252e", "#526c82", "#c7b2a7")][variant]
    dark, mid, light = palette
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640">
    <defs><linearGradient id="sky" x2="0.2" y2="1"><stop stop-color="{dark}"/><stop offset="1" stop-color="{mid}"/></linearGradient>
    <linearGradient id="fog" x2="0" y2="1"><stop stop-color="{light}" stop-opacity="0"/><stop offset="1" stop-color="{light}" stop-opacity=".18"/></linearGradient>
    <radialGradient id="glow"><stop stop-color="{light}" stop-opacity=".65"/><stop offset="1" stop-color="{light}" stop-opacity="0"/></radialGradient>
    <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".75" numOctaves="3" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope=".12"/></feComponentTransfer><feBlend in="SourceGraphic" mode="soft-light"/></filter>
    </defs><rect width="960" height="640" fill="url(#sky)"/><circle cx="675" cy="210" r="230" fill="url(#glow)"/>
    <circle cx="677" cy="173" r="60" fill="{light}" opacity=".64"/><path d="M0 260 Q150 190 260 250 T560 210 T960 250 L960 640 H0Z" fill="{dark}" opacity=".35"/>''']
    if variant == 1:
        for i in range(24):
            x, h, w = i * 47 - 35, rng.randint(90, 360), rng.randint(25, 72)
            parts.append(f'<rect x="{x}" y="{480-h}" width="{w}" height="{h}" fill="{dark}"/>')
            for y in range(490-h, 440, 23):
                parts.append(f'<path d="M{x+8} {y} h{max(8,w-16)}" stroke="{light if i%3==0 else mid}" stroke-width="3" opacity=".4"/>')
        parts.append(f'<path d="M250 392 H744 L780 565 H204Z" fill="#0b171b"/><rect x="270" y="384" width="470" height="42" fill="{light}"/><rect x="290" y="446" width="190" height="116" fill="{mid}" opacity=".9"/><rect x="502" y="446" width="196" height="116" fill="{light}" opacity=".65"/><path d="M546 446 V562 M640 446 V562 M502 496 H698" stroke="#1b3535" stroke-width="9"/><path d="M300 401 H704" stroke="#403a30" stroke-width="9"/>')
    elif variant == 2:
        for i in range(7):
            x = i * 180 - 150
            parts.append(f'<path d="M{x} 640 Q{x+60} {220+i%3*70} {x+150} {260+i%2*90} Q{x+210} 160 {x+300} 640Z" fill="{dark}" opacity="{.25+i*.06}"/>')
        parts.append(f'<path d="M0 570 Q220 430 450 570 T960 520 V640 H0Z" fill="#101f20"/><path d="M250 530 Q460 460 700 490" fill="none" stroke="{light}" stroke-width="2" opacity=".6"/><path d="M644 350 L666 185 L675 350 L662 370Z" fill="{light}" opacity=".6"/>')
    else:
        for layer in range(3):
            for i in range(8):
                x, y, w = i * 154 - 110 + layer * 38, 310 + layer * 91 + rng.randint(-45, 25), rng.randint(130, 190)
                parts.append(f'<path d="M{x} {y+15} V640 H{x+w} V{y+15}" fill="{dark}" opacity="{.4+layer*.22}"/><path d="M{x-26} {y+20} Q{x+24} {y+12} {x+w//2} {y-47} Q{x+w-24} {y+12} {x+w+26} {y+20} L{x+w+6} {y+30} H{x-6}Z" fill="{dark}"/>')
                if layer == 2:
                    for dx in range(25, w-10, 36):
                        parts.append(f'<rect x="{x+dx}" y="{y+50}" width="15" height="35" fill="{light}" opacity=".45"/><path d="M{x+dx-4} {y+60}h24" stroke="{dark}" stroke-width="3"/>')
        parts.append(f'<path d="M370 640 L550 385 L680 640" fill="{mid}" opacity=".45"/><path d="M435 640 L557 391 L610 640" fill="{light}" opacity=".1"/>')
        for x, y in [(174, 349), (770, 395), (872, 295), (322, 410)]:
            parts.append(f'<ellipse cx="{x}" cy="{y}" rx="42" ry="65" fill="url(#glow)"/><path d="M{x} {y-64} V{y-15}" stroke="{dark}" stroke-width="3"/><rect x="{x-10}" y="{y-15}" width="20" height="29" rx="7" fill="{light}"/><path d="M{x} {y+15}v20" stroke="{light}"/>')
    # The foreground figure, robe and umbrella create a readable cinematic silhouette.
    if variant != 1:
        px = 562 if variant != 2 else 478
        parts.append(f'<ellipse cx="{px}" cy="605" rx="75" ry="10" fill="{dark}"/><path d="M{px-13} 468 Q{px-32} 520 {px-42} 596 Q{px} 616 {px+44} 596 L{px+18} 467Z" fill="#0b151b"/><path d="M{px-10} 480 Q{px-2} 520 {px-14} 601 L{px+20} 601 L{px+10} 480Z" fill="{mid}"/><ellipse cx="{px}" cy="451" rx="14" ry="21" fill="{dark}"/><path d="M{px-14} 448 Q{px-20} 415 {px+10} 428 L{px+20} 490 L{px+4} 460Z" fill="#0a1117"/>')
        if variant != 2:
            parts.append(f'<path d="M{px+40} 420 V544" stroke="#b89b78" stroke-width="3"/><path d="M{px-69} 431 Q{px+20} 325 {px+132} 431 Q{px+28} 401 {px-69} 431Z" fill="#9a8671"/><path d="M{px+40} 367 V429 M{px+40} 367 L{px-15} 425 M{px+40} 367 L{px+90} 425" fill="none" stroke="#3f4647" opacity=".6"/>')
    for _ in range(100):
        x, y = rng.randint(0, 960), rng.randint(0, 640)
        parts.append(f'<path d="M{x} {y}l-7 31" stroke="{light}" stroke-width=".6" opacity=".16"/>')
    parts.append('<rect width="960" height="640" fill="url(#fog)"/><rect width="960" height="640" fill="transparent" filter="url(#grain)"/></svg>')
    return "".join(parts)
