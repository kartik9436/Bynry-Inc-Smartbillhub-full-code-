"""Read a text-bearing PDF whose glyphs are subset-encoded hex strings.

The document's text is written as `<2A> Tj` — font-subset GLYPH IDS, not ASCII —
so it is unreadable until each font's /ToUnicode CMap is applied. This walks the
object graph properly: page -> its /Resources /Font -> each font's /ToUnicode ->
the CMap's bfchar/bfrange tables, then decodes each page's content stream while
tracking the active font from `/Fx Tf`.
"""
import re, sys, zlib

data = open(sys.argv[1], 'rb').read()

OBJ = re.compile(rb'(\d+)\s+0\s+obj\b(.*?)\bendobj', re.S)
objs = {int(m.group(1)): m.group(2) for m in OBJ.finditer(data)}

def stream_of(body: bytes):
    m = re.search(rb'stream\r?\n', body)
    if not m:
        return None
    end = body.rfind(b'endstream')
    raw = body[m.end():end]
    try:
        return zlib.decompress(raw)
    except Exception:
        return raw

def cmap_of(num: int):
    """{glyph_code: text} from a /ToUnicode CMap object."""
    body = objs.get(num)
    if body is None:
        return {}
    s = stream_of(body) or b''
    out = {}
    for blk in re.findall(rb'beginbfchar(.*?)endbfchar', s, re.S):
        for src, dst in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            out[int(src, 16)] = bytes.fromhex(dst.decode()).decode('utf-16-be', 'replace')
    for blk in re.findall(rb'beginbfrange(.*?)endbfrange', s, re.S):
        for lo, hi, dst in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            a, b = int(lo, 16), int(hi, 16)
            base = int(dst, 16)
            for i in range(a, b + 1):
                try:
                    out[i] = chr(base + (i - a))
                except ValueError:
                    pass
    return out

TOUNI = re.compile(rb'/ToUnicode\s+(\d+)\s+0\s+R')

def fonts_of(resbody: bytes):
    """{'F5': {glyph: text}} for one page's resources."""
    m = re.search(rb'/Font\s*<<(.*?)>>', resbody, re.S)
    if not m:
        return {}
    out = {}
    for name, num in re.findall(rb'/([A-Za-z0-9]+)\s+(\d+)\s+0\s+R', m.group(1)):
        fb = objs.get(int(num), b'')
        t = TOUNI.search(fb)
        if t:
            out[name.decode()] = cmap_of(int(t.group(1)))
    return out

HEX = re.compile(rb'<([0-9A-Fa-f\s]*)>')

def decode_content(content: bytes, fonts: dict) -> str:
    lines, cur = [], {}
    for m in re.finditer(rb'BT(.*?)ET', content, re.S):
        blk = m.group(1)
        buf = []
        for tok in re.finditer(rb'/([A-Za-z0-9]+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f\s]*)>\s*Tj|\[((?:[^\[\]])*)\]\s*TJ', blk, re.S):
            if tok.group(1):
                cur = fonts.get(tok.group(1).decode(), {})
            else:
                chunks = [tok.group(2)] if tok.group(2) is not None else HEX.findall(tok.group(3) or b'')
                for h in chunks:
                    h = re.sub(rb'\s', b'', h or b'')
                    for i in range(0, len(h) - 1, 2):
                        buf.append(cur.get(int(h[i:i+2], 16), ''))
        if buf:
            lines.append(''.join(buf))
    return '\n'.join(lines)

pages = [(n, b) for n, b in objs.items() if re.search(rb'/Type\s*/Page[^sR]', b)]
pages.sort()
print(f"[pages found: {len(pages)}]", file=sys.stderr)
for idx, (num, body) in enumerate(pages, 1):
    res = re.search(rb'/Resources\s*(\d+)\s+0\s+R', body)
    resbody = objs.get(int(res.group(1)), b'') if res else body
    fonts = fonts_of(resbody)
    cont = re.search(rb'/Contents\s+(\d+)\s+0\s+R', body)
    if not cont:
        continue
    c = stream_of(objs.get(int(cont.group(1)), b'')) or b''
    txt = decode_content(c, fonts)
    print(f"\n═══════════ PAGE {idx} ═══════════")
    print(txt)
