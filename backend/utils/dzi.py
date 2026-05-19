import math

OVERLAP = 0


def max_level(width: int, height: int) -> int:
    return math.ceil(math.log2(max(width, height)))


def tile_bounds_in_original(
    col: int, row: int, level: int, max_lvl: int,
    img_w: int, img_h: int, tile_size: int = 256,
) -> tuple[int, int, int, int]:
    """Returns (x0, y0, x1, y1) in original image coordinates."""
    scale = 2 ** (max_lvl - level)
    x0 = col * tile_size * scale
    y0 = row * tile_size * scale
    x1 = min(x0 + tile_size * scale, img_w)
    y1 = min(y0 + tile_size * scale, img_h)
    return x0, y0, x1, y1


def tile_output_size(
    col: int, row: int, level: int, max_lvl: int,
    img_w: int, img_h: int, tile_size: int = 256,
) -> tuple[int, int]:
    """Returns (tw, th) — actual pixel size of this tile after downscaling."""
    scale = 2 ** (max_lvl - level)
    x0, y0, x1, y1 = tile_bounds_in_original(col, row, level, max_lvl, img_w, img_h, tile_size)
    tw = math.ceil((x1 - x0) / scale)
    th = math.ceil((y1 - y0) / scale)
    return max(tw, 1), max(th, 1)


def dzi_xml(width: int, height: int, tile_size: int = 256, fmt: str = "jpeg") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Image xmlns="http://schemas.microsoft.com/deepzoom/2008" '
        f'TileSize="{tile_size}" Overlap="{OVERLAP}" Format="{fmt}">\n'
        f'  <Size Width="{width}" Height="{height}" />\n'
        "</Image>"
    )
