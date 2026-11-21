"""Optional maintainer tool: build the original, synthetic MDD diagnostic font.

Requires fontTools only when regenerating the bundled font, never for user tests.
ASCII A/B/C deliberately render as triangle/plus/diamond to expose fallback.
"""
from pathlib import Path


def main():
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    root = Path(__file__).resolve().parents[1]
    outlines = {
        '.notdef': [(100,0),(900,0),(900,800),(100,800)],
        'triangle': [(100,0),(900,0),(500,800)],
        'plus': [(400,0),(600,0),(600,300),(900,300),(900,500),(600,500),
                 (600,800),(400,800),(400,500),(100,500),(100,300),(400,300)],
        'diamond': [(500,0),(900,400),(500,800),(100,400)],
    }
    glyphs = {}
    for name, points in outlines.items():
        pen = TTGlyphPen(None); pen.moveTo(points[0])
        for point in points[1:]: pen.lineTo(point)
        pen.closePath(); glyphs[name] = pen.glyph()
    font = FontBuilder(1000, isTTF=True)
    font.setupGlyphOrder(list(outlines))
    font.setupCharacterMap({65:'triangle',66:'plus',67:'diamond'})
    font.setupGlyf(glyphs)
    font.setupHorizontalMetrics({name:(1000,100) for name in outlines})
    font.setupHorizontalHeader(ascent=900, descent=-100)
    font.setupNameTable({'familyName':'Studio MDD Probe', 'styleName':'Regular',
        'uniqueFontIdentifier':'StudioMddProbe-Original-1', 'fullName':'Studio MDD Probe Regular',
        'psName':'StudioMddProbe-Regular', 'version':'Version 1.000',
        'licenseDescription':'Original diagnostic outlines; distributed under the MIT license in FONT-LICENSE.txt.'})
    font.setupOS2(sTypoAscender=900,sTypoDescender=-100,usWinAscent=900,usWinDescent=100,fsType=0)
    font.setupPost(); font.setupMaxp()
    font.font.recalcTimestamp = False
    font.font['head'].created = font.font['head'].modified = 3786912000
    path = root/'baseline/resource-probe/studio-probe.ttf'; path.parent.mkdir(parents=True,exist_ok=True)
    font.save(path); print(path)


if __name__ == '__main__': main()
