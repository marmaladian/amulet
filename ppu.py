import numpy as np
import pygame

from device import Device

# --- geometry / map constants ---
SCREEN_W, SCREEN_H = 224, 256
TILE_W, TILE_H = 8, 8
MAP_W, MAP_H = 28, 32
MAX_TILES = 256

# --- memory map (CPU-visible addresses) ---
TILEMAP_IDX_BASE = 0xA000           # 896 bytes
TILEMAP_ATT_BASE = 0xA380           # 896 bytes
OAM_BASE         = 0xA800           # 16 sprites x 16B = 256B
PALETTE_BASE     = 0xA900           # 32B (16 x RGB444)
TILESET_BASE     = 0xB000           # 8192B (256 tiles x 32B)
TILESET_SIZE     = 8192

# --- PPU registers (IO) ---
DISP_CTRL = 0xE000
STATUS    = 0xE001
SCROLL_X  = 0xE002
SCROLL_Y  = 0xE003
# E004..E009 reserved for DMA in future


class PPU(Device):
    """PPU as a bus device: owns VRAM regions + IO regs and renders to a pygame Surface."""
    def __init__(self, scale=3):
        self.scale = scale
        # IO regs
        self.disp_ctrl = 0
        self.status = 0
        self.scroll_x = 0
        self.scroll_y = 0

        # VRAM blocks (CPU view mapped below)
        self.tilemap_idx = bytearray(MAP_W * MAP_H)      # 0xA000
        self.tilemap_att = bytearray(MAP_W * MAP_H)      # 0xA380
        self.oam         = bytearray(16 * 16)            # 0xA800
        self._pal_raw    = bytearray(32)                 # 0xA900 (RGB444 packed LE)
        self.tileset     = bytearray(TILESET_SIZE)       # 0xB000

        # Derived palette: 16 x (r,g,b) in 8-bit
        self.palette = [(0, 0, 0)] * 16
        self._recalc_palette()

        # Framebuffer (numpy) and pygame surface
        self._fb = np.zeros((SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
        self.surface = pygame.Surface((SCREEN_W, SCREEN_H))

    # ---------- Bus device plumbing ----------
    def handles(self, addr: int) -> bool:
        return (
            (TILEMAP_IDX_BASE <= addr < TILEMAP_IDX_BASE + MAP_W*MAP_H) or
            (TILEMAP_ATT_BASE <= addr < TILEMAP_ATT_BASE + MAP_W*MAP_H) or
            (OAM_BASE         <= addr < OAM_BASE         + 16*16)       or
            (PALETTE_BASE     <= addr < PALETTE_BASE     + 32)          or
            (TILESET_BASE     <= addr < TILESET_BASE     + TILESET_SIZE) or
            (DISP_CTRL        <= addr <= SCROLL_Y)
        )

    def read8(self, addr: int) -> int:
        if addr == DISP_CTRL: return self.disp_ctrl
        if addr == STATUS:    return self.status
        if addr == SCROLL_X:  return self.scroll_x
        if addr == SCROLL_Y:  return self.scroll_y

        if TILEMAP_IDX_BASE <= addr < TILEMAP_IDX_BASE + MAP_W*MAP_H:
            return self.tilemap_idx[addr - TILEMAP_IDX_BASE]
        if TILEMAP_ATT_BASE <= addr < TILEMAP_ATT_BASE + MAP_W*MAP_H:
            return self.tilemap_att[addr - TILEMAP_ATT_BASE]
        if OAM_BASE <= addr < OAM_BASE + 16*16:
            return self.oam[addr - OAM_BASE]
        if PALETTE_BASE <= addr < PALETTE_BASE + 32:
            return self._pal_raw[addr - PALETTE_BASE]
        if TILESET_BASE <= addr < TILESET_BASE + TILESET_SIZE:
            return self.tileset[addr - TILESET_BASE]
        return 0

    def write8(self, addr: int, val: int):
        v = val & 0xFF
        if addr == DISP_CTRL: self.disp_ctrl = v; return
        if addr == STATUS:    self.status = v;    return  # usually read-only; fine for now
        if addr == SCROLL_X:  self.scroll_x = v;  return
        if addr == SCROLL_Y:  self.scroll_y = v;  return

        if TILEMAP_IDX_BASE <= addr < TILEMAP_IDX_BASE + MAP_W*MAP_H:
            self.tilemap_idx[addr - TILEMAP_IDX_BASE] = v; return
        if TILEMAP_ATT_BASE <= addr < TILEMAP_ATT_BASE + MAP_W*MAP_H:
            self.tilemap_att[addr - TILEMAP_ATT_BASE] = v; return
        if OAM_BASE <= addr < OAM_BASE + 16*16:
            self.oam[addr - OAM_BASE] = v; return
        if PALETTE_BASE <= addr < PALETTE_BASE + 32:
            self._pal_raw[addr - PALETTE_BASE] = v
            self._recalc_palette()
            return
        if TILESET_BASE <= addr < TILESET_BASE + TILESET_SIZE:
            self.tileset[addr - TILESET_BASE] = v; return

    # ---------- Palette helpers ----------
    def _recalc_palette(self):
        pals = []
        raw = self._pal_raw
        for i in range(16):
            lo = raw[i*2]
            hi = raw[i*2 + 1]
            word = ((hi << 8) | lo) & 0x0FFF  # 0x0RGB
            r = (word >> 8) & 0xF
            g = (word >> 4) & 0xF
            b = (word >> 0) & 0xF
            pals.append((r * 17, g * 17, b * 17))
        self.palette = pals

    # ---------- Rendering ----------
    def render_frame(self):
        """Compose BG then sprites into self._fb and upload to pygame surface."""
        # Pass 1: background
        bg_prio = np.zeros((SCREEN_H, SCREEN_W), dtype=np.bool_)
        # Iterate per pixel (simple, readable; optimise later)
        for y in range(SCREEN_H):
            sy = (y + self.scroll_y) % SCREEN_H
            ty = sy // TILE_H
            py = sy % TILE_H
            row_base_idx = ty * MAP_W
            for x in range(SCREEN_W):
                sx = (x + self.scroll_x) % SCREEN_W
                tx = sx // TILE_W
                px = sx % TILE_W
                idx = self.tilemap_idx[row_base_idx + tx]
                attr = self.tilemap_att[row_base_idx + tx]
                hflip = (attr >> 4) & 1
                vflip = (attr >> 5) & 1
                prio  = (attr >> 6) & 1

                # fetch tile row
                row = self._fetch_tile_row(idx, py, bool(hflip), bool(vflip))
                ci = row[px]
                self._fb[y, x] = self.palette[ci]
                bg_prio[y, x] = bool(prio)

        # Pass 2: sprites (ID order; priority vs BG via bits)
        for i in range(16):
            base = i * 16
            x0   = self.oam[base + 0]
            y0   = self.oam[base + 1]
            tile = self.oam[base + 2]
            attr = self.oam[base + 3]
            hflip = bool((attr >> 4) & 1)
            vflip = bool((attr >> 5) & 1)
            size  = 16 if ((attr >> 6) & 1) else 8
            spr_prio = bool((attr >> 7) & 1)

            for dy in range(size):
                py = y0 + dy
                if py < 0 or py >= SCREEN_H: continue
                row_in_tile = dy % 8
                if vflip: row_in_tile = 7 - row_in_tile
                tile_row_offset = (dy // 8) * 2  # for 16x16: next row of tiles

                # prefetch both (or one) tile-rows for this scan
                # we’ll fetch per 8 columns to stay simple
                for dx in range(size):
                    px = x0 + dx
                    if px < 0 or px >= SCREEN_W: continue
                    col_in_tile = dx % 8
                    if hflip: col_in_tile = 7 - col_in_tile
                    tile_col_offset = (dx // 8)
                    tid = (tile + tile_row_offset + tile_col_offset) & 0xFF
                    row = self._fetch_tile_row(tid, row_in_tile, False, False)
                    ci = row[col_in_tile]
                    if ci == 0:  # transparent
                        continue
                    if not spr_prio and bg_prio[py, px]:
                        continue
                    self._fb[py, px] = self.palette[ci]

        # Upload to pygame Surface (pygame surfarray expects (w,h,3); we transpose)
        pygame.surfarray.blit_array(self.surface, self._fb.swapaxes(0, 1))
        return self.surface

    # --- tile decode: returns np.uint8[8] colour indices for a tile row ---
    def _fetch_tile_row(self, tile_id: int, row: int, hflip: bool, vflip: bool) -> np.ndarray:
        if vflip: row = 7 - row
        base = (tile_id & 0xFF) * 32 + row * 4   # 4 bytes per row (8 px / 2 px per byte)
        out = np.empty(8, dtype=np.uint8)
        # slice from tileset bytearray
        for i in range(4):
            byte = self.tileset[base + i]
            out[i*2]   = (byte >> 4) & 0xF
            out[i*2+1] = byte & 0xF
        if hflip:
            out = out[::-1]
        return out

from typing import Iterable, Sequence, Tuple, Dict, Optional
import numpy as np

# ---------- 4bpp tile packing ----------

def pack_tile_4bpp(pixels_8x8: Sequence[Sequence[int]]) -> bytes:
    """
    pixels_8x8: 8 rows of 8 colour indices (0..15).
    Returns: 32 bytes, packed two pixels per byte (high nibble = left pixel).
    """
    arr = np.array(pixels_8x8, dtype=np.uint8)
    assert arr.shape == (8, 8), "tile must be 8x8"
    assert (arr < 16).all(), "colour indices must be 0..15"
    out = bytearray(32)
    k = 0
    for y in range(8):
        for x in range(0, 8, 2):
            out[k] = ((arr[y, x] & 0xF) << 4) | (arr[y, x+1] & 0xF)
            k += 1
    return bytes(out)

def make_solid_tile(ci: int) -> bytes:
    """A solid-colour tile of colour index ci (0..15)."""
    return pack_tile_4bpp([[ci]*8 for _ in range(8)])

def make_checker_tile(a: int, b: int) -> bytes:
    """Simple 2×2 checkerboard of colours a/b."""
    pix = [[(a if ((x>>1)+(y>>1)) & 1 == 0 else b) for x in range(8)] for y in range(8)]
    return pack_tile_4bpp(pix)

def make_stripe_tile(a: int, b: int, horizontal: bool=True) -> bytes:
    """Striped tile alternating a/b each row or column."""
    if horizontal:
        pix = [[(a if (y & 1)==0 else b) for x in range(8)] for y in range(8)]
    else:
        pix = [[(a if (x & 1)==0 else b) for x in range(8)] for y in range(8)]
    return pack_tile_4bpp(pix)

# ---------- palette helpers (RGB444 packed 0x0RGB, little-endian) ----------

def palette_entry_rgb444(r: int, g: int, b: int) -> Tuple[int, int]:
    """
    r,g,b in 0..15. Returns (lo, hi) bytes for 0x0RGB packed little-endian.
    """
    word = ((r & 0xF) << 8) | ((g & 0xF) << 4) | (b & 0xF)
    return (word & 0xFF), ((word >> 8) & 0xFF)

def write_palette(ppu, entries: Iterable[Tuple[int,int,int]]):
    """
    entries: iterable of up to 16 (r,g,b) tuples, values 0..15.
    Writes into PPU palette RAM and recalculates RGB888 cache.
    """
    i = 0
    for (r,g,b) in entries:
        lo, hi = palette_entry_rgb444(r,g,b)
        ppu.write8(0xA900 + i*2, lo)
        ppu.write8(0xA900 + i*2 + 1, hi)
        i += 1
        if i >= 16: break
    # ensure derived palette is updated
    # (PPU.write8 already calls _recalc_palette())

# ---------- tileset loaders ----------

def write_tile(ppu, tile_id: int, tile_bytes: bytes):
    """Write one 8×8×4bpp tile (32 bytes) into tileset VRAM."""
    assert 0 <= tile_id < 256
    assert len(tile_bytes) == 32
    base = 0xB000 + tile_id * 32
    for i, b in enumerate(tile_bytes):
        ppu.write8(base + i, b)

def load_tileset(ppu, tiles: Dict[int, bytes]):
    """tiles: {tile_id: packed32bytes}"""
    for tid, blob in tiles.items():
        write_tile(ppu, tid, blob)

def load_tileset_sequential(ppu, blob: bytes, start_id: int = 0):
    """Load a contiguous blob of N tiles (N*32 bytes) starting at start_id."""
    assert len(blob) % 32 == 0
    n = len(blob) // 32
    for i in range(n):
        write_tile(ppu, start_id + i, blob[i*32:(i+1)*32])

# ---------- tilemap loaders ----------

MAP_W, MAP_H = 28, 32

def set_tilemap_indices(ppu, indices_2d: Sequence[Sequence[int]]):
    """indices_2d: MAP_H rows × MAP_W entries of tile IDs (0..255)."""
    assert len(indices_2d) == MAP_H
    for y, row in enumerate(indices_2d):
        assert len(row) == MAP_W
        for x, tid in enumerate(row):
            ppu.write8(0xA000 + y*MAP_W + x, tid & 0xFF)

def set_tilemap_attrs(ppu, attrs_2d: Optional[Sequence[Sequence[int]]] = None, default_attr: int = 0):
    """
    attrs_2d optional: MAP_H × MAP_W bytes.
    If None, fills with default_attr.
    """
    if attrs_2d is None:
        for off in range(MAP_W*MAP_H):
            ppu.write8(0xA380 + off, default_attr & 0xFF)
        return
    assert len(attrs_2d) == MAP_H
    for y, row in enumerate(attrs_2d):
        assert len(row) == MAP_W
        for x, val in enumerate(row):
            ppu.write8(0xA380 + y*MAP_W + x, val & 0xFF)

def make_chequer_indices(w=MAP_W, h=MAP_H, t0=0, t1=1) -> np.ndarray:
    """Alternating tile IDs t0/t1 across the map."""
    m = np.zeros((h, w), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            m[y, x] = t0 if ((x + y) & 1) == 0 else t1
    return m

def make_attr_grid(w=MAP_W, h=MAP_H, *, hflip_cols: int = 0, vflip_rows: int = 0, prio_border: int = 0) -> np.ndarray:
    """
    Build an attribute grid with playful flags set:
    - hflip set on first hflip_cols columns
    - vflip set on first vflip_rows rows
    - priority set on a border of prio_border tiles around the edges
    Bits: 0..3 palette bank (0), 4=hflip, 5=vflip, 6=priority, 7=reserved
    """
    A_H = 1 << 4; A_V = 1 << 5; A_P = 1 << 6
    m = np.zeros((h, w), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            a = 0
            if x < hflip_cols: a |= A_H
            if y < vflip_rows: a |= A_V
            if prio_border and (x < prio_border or x >= w-prio_border or y < prio_border or y >= h-prio_border):
                a |= A_P
            m[y, x] = a
    return m

def sprite_attr(*, palette_bank: int = 0, hflip=False, vflip=False, size16=False, prio=False) -> int:
    """
    Build sprite attribute byte.
    bit0..3 palette bank (0..15) (reserved for future)
    bit4 hflip, bit5 vflip, bit6 size (1=16×16), bit7 priority (1=in front)
    """
    a = (palette_bank & 0xF)
    if hflip: a |= (1 << 4)
    if vflip: a |= (1 << 5)
    if size16: a |= (1 << 6)
    if prio: a |= (1 << 7)
    return a & 0xFF

def place_sprite(ppu, index: int, x: int, y: int, tile_id: int, attr: int):
    """Write one sprite into OAM at slot index (0..15)."""
    assert 0 <= index < 16
    base = 0xA800 + index * 16
    ppu.write8(base + 0, x & 0xFF)
    ppu.write8(base + 1, y & 0xFF)
    ppu.write8(base + 2, tile_id & 0xFF)
    ppu.write8(base + 3, attr & 0xFF)
    # bytes 4..15 reserved/unused for now

# ---------- Demo initialisation ----------
def init_demo_palette(ppu):
    """
    A readable 16-colour palette: dark→bright ramp with distinct hues.
    Values are 0..15 in RGB444 space.
    """
    hues = [
        (0,0,0), (2,2,2), (4,4,4), (8,8,8), (12,12,12), (15,15,15),  # greys
        (15,0,0), (0,15,0), (0,0,15),                                # primaries
        (15,15,0), (0,15,15), (15,0,15),                             # secondaries
        (15,6,0), (10,0,15), (0,12,6), (15,8,8)                      # accents
    ]
    write_palette(ppu, hues)

def init_demo_tileset(ppu):
    """
    Populate tile 0..7 with simple patterns; keep 0 with colour 0 so sprites can be transparent if they use it.
    """
    load_tileset(ppu, {
        0: make_solid_tile(0),           # fully transparent-looking if used in sprites (colour 0)
        1: make_solid_tile(7),
        2: make_solid_tile(10),
        3: make_checker_tile(3, 12),
        4: make_checker_tile(1, 5),
        5: make_stripe_tile(2, 0, horizontal=True),
        6: make_stripe_tile(4, 0, horizontal=False),
        7: pack_tile_4bpp([[ (x+y) & 0xF for x in range(8)] for y in range(8)]),  # gradient tile
    })

def init_demo_tilemap(ppu):
    """
    Fill the background with a repeating 4×2 block of tiles (1..7) with some flips and a priority border.
    """
    idx = np.zeros((MAP_H, MAP_W), dtype=np.uint8)
    bank = [1,2,3,4,5,6,7,3]  # 8-tile ring
    for y in range(MAP_H):
        for x in range(MAP_W):
            idx[y, x] = bank[(x//2 + y//2) % len(bank)]
    set_tilemap_indices(ppu, idx)

    attrs = make_attr_grid(MAP_W, MAP_H, hflip_cols=4, vflip_rows=4, prio_border=1)
    set_tilemap_attrs(ppu, attrs)

def init_demo_sprites(ppu):
    """
    Place three sprites demonstrating flips, size, and priority.
    """
    # Small sprite 8×8
    place_sprite(ppu, 0, x=40,  y=40,  tile_id=7, attr=sprite_attr(hflip=False, vflip=False, size16=False, prio=True))
    # Flipped sprite 8×8
    place_sprite(ppu, 1, x=60,  y=40,  tile_id=7, attr=sprite_attr(hflip=True, vflip=True, size16=False, prio=False))
    # 16×16 sprite (2×2 tiles starting at tile 3)
    place_sprite(ppu, 2, x=100, y=80,  tile_id=3, attr=sprite_attr(size16=True, prio=True))

def init_demo_scene(ppu):
    init_demo_palette(ppu)        # overwrite with colourful palette
    init_demo_tileset(ppu)
    init_demo_tilemap(ppu)
    init_demo_sprites(ppu)
    # turn display on (BG+sprites), enable vblank irq bit if you use it
    DISP_CTRL = 0xE000
    bg = 1<<2; spr = 1<<1; on = 1<<0
    ppu.write8(DISP_CTRL, bg | spr | on)

def move_sprite_x(ppu, index: int, x: int):
    base = 0xA800 + index * 16
    ppu.write8(base + 0, x & 0xFF)