"""Render PDF pages to PNG with no imaging library.

Pillow could not be installed (network timeout), so this writes the PNG from
pypdfium2's raw bitmap using zlib and struct alone.

⚠ The channel count is READ FROM THE BITMAP, never assumed. The first draft
assumed BGRA, wrote a 4-channel header over 3-channel BGR data, and produced a
file that is structurally a valid PNG and visually garbage — a header that
passes every check while the pixels are nonsense.
"""
import struct, sys, zlib
import pypdfium2 as pdfium

def write_png(path, w, h, stride, buf, nch):
    mv = memoryview(buf)
    raw = bytearray()
    for y in range(h):
        row = bytearray(mv[y*stride:y*stride + w*nch])
        row[0::nch], row[2::nch] = row[2::nch], row[0::nch]   # BGR(A) -> RGB(A)
        raw.append(0)
        raw += row
    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))
    colortype = 6 if nch == 4 else 2
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, colortype, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(bytes(raw), 6))
           + chunk(b'IEND', b''))
    open(path, 'wb').write(png)

src, outdir, scale = sys.argv[1], sys.argv[2], float(sys.argv[3])
pages = [int(x) for x in sys.argv[4].split(',')]
doc = pdfium.PdfDocument(src)
for n in pages:
    bm = doc[n-1].render(scale=scale)
    nch = bm.n_channels
    write_png(f"{outdir}/p{n:03d}.png", bm.width, bm.height, bm.stride, bm.buffer, nch)
    print(f"p{n:03d}.png {bm.width}x{bm.height} ch={nch}")
