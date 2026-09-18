"""What each station is clad in.

No two stations on the real network are tiled alike, so none of these are
either. A station's look is worked out from its name, which means it is the
same every time you walk into it and survives the map being reordered, and a
handful of the ones with a look of their own are set by hand.

This module holds only the choice of colours and patterns. Where any of it
goes on screen is station_layout's business.
"""

import zlib

from pydantic import BaseModel, Field

Color = tuple[int, int, int]


class Palette(BaseModel):
    """The colours one station is clad in.

    Floors stay in the middle of the range whatever the walls do: people
    stand on them, and a floor as light as the walls would swallow them."""

    name: str
    cap: Color = Field(description="the lit strip along the top of the wall")
    wall: Color
    band: Color = Field(description="the band across the top of the wall face")
    dark: Color = Field(description="the shadow at the foot of the wall")
    floor_a: Color
    floor_b: Color
    grout: Color
    accent: Color = Field(description="the azulejo panels")
    pillar: Color


PALETTES: dict[str, Palette] = {
    p.name: p for p in [
        Palette(name="pedra", cap=(152, 148, 142), wall=(128, 120, 106), band=(108, 100, 88),
                dark=(96, 90, 80), floor_a=(98, 92, 82), floor_b=(92, 86, 76), grout=(80, 74, 66),
                accent=(214, 202, 172), pillar=(150, 146, 140)),
        Palette(name="azul", cap=(214, 220, 232), wall=(186, 198, 218), band=(64, 100, 158),
                dark=(140, 152, 178), floor_a=(112, 120, 136), floor_b=(104, 112, 128), grout=(88, 96, 110),
                accent=(40, 78, 152), pillar=(170, 180, 198)),
        Palette(name="verde", cap=(150, 170, 144), wall=(112, 136, 112), band=(72, 98, 74),
                dark=(84, 104, 84), floor_a=(96, 108, 92), floor_b=(90, 102, 86), grout=(74, 86, 72),
                accent=(198, 224, 178), pillar=(140, 158, 136)),
        Palette(name="terracota", cap=(196, 148, 118), wall=(166, 110, 84), band=(124, 76, 56),
                dark=(126, 80, 60), floor_a=(126, 94, 78), floor_b=(118, 88, 72), grout=(96, 70, 58),
                accent=(246, 202, 148), pillar=(184, 148, 122)),
        Palette(name="vinho", cap=(168, 136, 152), wall=(126, 88, 106), band=(88, 58, 74),
                dark=(96, 66, 80), floor_a=(104, 84, 96), floor_b=(98, 78, 90), grout=(82, 64, 76),
                accent=(232, 186, 208), pillar=(158, 132, 146)),
        Palette(name="areia", cap=(224, 210, 180), wall=(198, 182, 150), band=(150, 132, 100),
                dark=(158, 142, 112), floor_a=(126, 116, 96), floor_b=(118, 108, 90), grout=(98, 90, 74),
                accent=(140, 112, 64), pillar=(196, 184, 160)),
        Palette(name="turquesa", cap=(148, 188, 190), wall=(96, 142, 146), band=(56, 98, 104),
                dark=(70, 108, 112), floor_a=(92, 116, 118), floor_b=(86, 110, 112), grout=(72, 92, 94),
                accent=(198, 236, 234), pillar=(136, 174, 176)),
        Palette(name="aco", cap=(174, 180, 190), wall=(118, 124, 136), band=(84, 90, 102),
                dark=(92, 98, 110), floor_a=(96, 100, 112), floor_b=(90, 94, 106), grout=(74, 78, 90),
                accent=(198, 214, 232), pillar=(154, 160, 172)),
        Palette(name="ocre", cap=(210, 182, 118), wall=(172, 140, 76), band=(126, 100, 50),
                dark=(132, 106, 56), floor_a=(120, 102, 70), floor_b=(112, 96, 66), grout=(94, 80, 56),
                accent=(252, 226, 156), pillar=(190, 166, 118)),
        Palette(name="noite", cap=(118, 128, 148), wall=(82, 92, 112), band=(52, 60, 78),
                dark=(62, 70, 88), floor_a=(80, 86, 100), floor_b=(74, 80, 94), grout=(62, 68, 80),
                accent=(168, 194, 232), pillar=(112, 122, 142)),
        # Olaias is the loudest station on the network and gets to stay that way.
        Palette(name="olaias", cap=(226, 176, 96), wall=(148, 72, 86), band=(74, 92, 148),
                dark=(104, 52, 62), floor_a=(112, 84, 96), floor_b=(104, 78, 90), grout=(84, 62, 72),
                accent=(250, 214, 92), pillar=(190, 96, 84)),
    ]
}

# Palettes kept for the station they were mixed for, and left out of the pool
# the rest of the network draws from: a one-off that turns up eight times is
# not a one-off.
SIGNATURE_ONLY = ("olaias",)

# How the wall face between the band and its foot is laid out.
PATTERNS = ("courses", "squares", "bands", "diamonds", "stripes", "mosaic")

# What is painted on the tile panels at either end of the wall.
MOTIFS = ("waves", "chevron", "circles", "arches", "lattice")

# The ones with a look of their own, rather than one worked out from the name.
SIGNATURES: dict[str, tuple[str, str, str]] = {
    "Rossio": ("azul", "squares", "waves"),             # the wave calçada outside it
    "Baixa-Chiado": ("azul", "squares", "arches"),
    "Olaias": ("olaias", "diamonds", "chevron"),
    "Oriente": ("aco", "stripes", "lattice"),
    "Campo Pequeno": ("terracota", "courses", "arches"),  # under the bullring
    "Cais do Sodré": ("turquesa", "bands", "waves"),      # down by the river
    "Parque": ("verde", "mosaic", "lattice"),
    "Aeroporto": ("aco", "bands", "chevron"),
    "Marquês de Pombal": ("ocre", "courses", "lattice"),
    "Terreiro do Paço": ("azul", "bands", "arches"),
}


class StationStyle(BaseModel):
    palette: Palette
    pattern: str
    motif: str


def underground(color: Color, k: float = 0.42) -> Color:
    """The same cladding seen in the dark of the entrance passage.

    Scaled rather than shaded by a fixed amount: the palettes run from sand
    to plum, and taking the same number off every one of them would leave
    half of them black and the other half still bright."""
    return tuple(round(c * k) for c in color)


def _build(name: str) -> StationStyle:
    if name in SIGNATURES:
        palette, pattern, motif = SIGNATURES[name]
        return StationStyle(palette=PALETTES[palette], pattern=pattern, motif=motif)
    # crc32, not hash(): hash() of a string is salted per process, so the same
    # station came out a different colour every time the game was started.
    key = zlib.crc32(name.encode("utf-8"))
    palettes = [n for n in PALETTES if n not in SIGNATURE_ONLY]
    return StationStyle(
        palette=PALETTES[palettes[key % len(palettes)]],
        pattern=PATTERNS[key // len(palettes) % len(PATTERNS)],
        motif=MOTIFS[key // (len(palettes) * len(PATTERNS)) % len(MOTIFS)],
    )


_styles: dict[str, StationStyle] = {}


def style_for(name: str) -> StationStyle:
    """The look of one station. Worked out once, then kept."""
    style = _styles.get(name)
    if style is None:
        style = _styles[name] = _build(name)
    return style
