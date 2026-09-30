from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "files" / "localization_ko"
TEMPLATE_DIR = ROOT / "files" / "fission" / "art" / "polish" / "intrface"
OUTPUT_DIR = ROOT / "files" / "fission" / "art" / "korean" / "intrface"
PALETTE_PATH = SOURCE_DIR / "Fallout.act"

def load_palette():
    raw = PALETTE_PATH.read_bytes()
    if len(raw) < 768:
        raise ValueError("Fallout.act is shorter than 768 bytes")
    return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, 229 * 3, 3)]

def make_mapper(palette):
    exact = {rgb: i for i, rgb in enumerate(palette)}
    cache = {}
    def map_rgb(rgb):
        if rgb in exact:
            return exact[rgb]
        if rgb in cache:
            return cache[rgb]
        index = min(range(len(palette)), key=lambda i:
            sum((rgb[c] - palette[i][c]) ** 2 for c in range(3)))
        cache[rgb] = index
        return index
    return map_rgb
def read_bmp(path, map_rgb):
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError(f"{path.name}: not a BMP")
    offset = struct.unpack_from("<I", data, 10)[0]
    dib_size, width, height, planes, bpp = struct.unpack_from("<IiiHH", data, 14)
    if dib_size < 40 or planes != 1 or bpp not in (24, 32):
        raise ValueError(f"{path.name}: unsupported BMP format")
    abs_height = abs(height)
    row_stride = ((width * bpp + 31) // 32) * 4
    bytes_per_pixel = bpp // 8
    pixels = bytearray()
    for y in range(abs_height):
        source_y = y if height < 0 else abs_height - 1 - y
        row = offset + source_y * row_stride
        for x in range(width):
            pos = row + x * bytes_per_pixel
            blue, green, red = data[pos:pos + 3]
            pixels.append(map_rgb((red, green, blue)))
    return width, abs_height, bytes(pixels)

def template_map():
    return {p.stem.lower(): p for p in TEMPLATE_DIR.iterdir()
            if p.is_file() and p.suffix.lower() == ".frm"}

def build_frm(template_path, width, height, pixels):
    raw = bytearray(template_path.read_bytes())
    if len(raw) < 74:
        raise ValueError(f"{template_path.name}: FRM too short")
    version, fps, action_frame, frame_count = struct.unpack_from(">IHHH", raw, 0)
    if version != 4 or frame_count != 1:
        raise ValueError(f"{template_path.name}: unsupported FRM layout")
    frame_width, frame_height, frame_size, x_off, y_off = struct.unpack_from(">HHIhh", raw, 62)
    if (frame_width, frame_height) != (width, height):
        raise ValueError(
            f"{template_path.name}: template {frame_width}x{frame_height}, BMP {width}x{height}")
    if len(pixels) != width * height:
        raise ValueError(f"{template_path.name}: unexpected pixel count")

    frame = struct.pack(">HHIhh", width, height, len(pixels), x_off, y_off) + pixels
    header = raw[:62]
    struct.pack_into(">I", header, 58, len(frame))
    return bytes(header) + frame

def main():
    palette = load_palette()
    map_rgb = make_mapper(palette)
    templates = template_map()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    built = []
    for bmp_path in sorted(SOURCE_DIR.glob("*.bmp"), key=lambda p: p.name.lower()):
        template_path = templates.get(bmp_path.stem.lower())
        if template_path is None:
            raise FileNotFoundError(f"No Polish FRM template for {bmp_path.name}")
        width, height, pixels = read_bmp(bmp_path, map_rgb)
        frm = build_frm(template_path, width, height, pixels)
        output_path = OUTPUT_DIR / template_path.name
        output_path.write_bytes(frm)
        built.append(output_path)
        print(f"{bmp_path.name} -> {output_path.relative_to(ROOT)} ({width}x{height})")

    print(f"Built {len(built)} Korean UI FRM files.")

if __name__ == "__main__":
    main()
