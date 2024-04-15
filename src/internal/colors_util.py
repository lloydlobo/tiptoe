from functools import lru_cache
from typing import Final


@lru_cache(maxsize=None)
def hex_to_rgb(s: str) -> tuple[int, int, int]:
    """
    HEX to RGB color:
        The red, green and blue use 8 bits each, which have integer values from 0 to 255.
        So the number of colors that can be generated is:
        256×256×256 = 16777216 = 100000016
        Hex to RGB conversion
          - Get the 2 left digits of the hex color code and convert to decimal value to get the red color level.
          - Get the 2 middle digits of the hex color code and convert to decimal value to get the green color level.
          - Get the 2 right digits of the hex color code and convert to decimal value to get the blue color level.
        Convert red hex color code FF0000 to RGB color: Hex = FF0000
        R = FF16 = 25510, G = 0016 = 010, B = 0016 = 010
        RGB = (255, 0, 0)
        Source: https://www.rapidtables.com/convert/color/how-hex-to-rgb.html

    >>> assert hex_to_rgb("#ff0000") == (255, 0, 0)
    >>> assert hex_to_rgb("ff0000") == (255, 0, 0)
    >>> assert hex_to_rgb("#ffd700") == (255, 215, 0)
    >>> assert hex_to_rgb("#FFD700") == (255, 215, 0)
    """
    base: Final = 16

    if (n := len(s)) and n == 7:
        if s[0] == "#":
            s = s[1:]
            assert len(s) == (n - 1)
        else:
            raise ValueError(f"expected valid hex format string. got {s}")

    return (int(s[0:2], base), int(s[2:4], base), int(s[4:6], base))


@lru_cache(maxsize=None)
def hsl_to_rgb(h: int, s: float, l: float) -> tuple[int, int, int]:
    """
    Constraints: 0 ≤ H < 360, 0 ≤ S ≤ 1 and 0 ≤ L ≤ 1

    >>> assert hsl_to_rgb(0, 0, 0) == (0, 0, 0)             # black
    >>> assert hsl_to_rgb(0, 0, 1) == (255, 255, 255)       # white
    >>> assert hsl_to_rgb(0, 1, 0.5) == (255, 0, 0)         # red
    >>> assert hsl_to_rgb(120, 1, 0.5) == (0, 255, 0)       # lime green
    >>> assert hsl_to_rgb(240, 1, 0.5) == (0, 0, 255)       # blue
    >>> assert hsl_to_rgb(60, 1, 0.5) == (255, 255, 0)      # yellow
    >>> assert hsl_to_rgb(180, 1, 0.5) == (0, 255, 255)     # cyan
    >>> assert hsl_to_rgb(300, 1, 0.5) == (255, 0, 255)     # magenta
    >>> assert hsl_to_rgb(0, 0, 0.75) == (191, 191, 191)    # silver
    >>> assert hsl_to_rgb(0, 0, 0.5) == (128, 128, 128)     # gray
    >>> assert hsl_to_rgb(0, 1, 0.25) == (128, 0, 0)        # maroon
    >>> assert hsl_to_rgb(60, 1, 0.25) == (128, 128, 0)     # olive
    >>> assert hsl_to_rgb(120, 1, 0.25) == (0, 128, 0)      # green
    >>> assert hsl_to_rgb(300, 1, 0.25) == (128, 0, 128)    # purple
    >>> assert hsl_to_rgb(180, 1, 0.25) == (0, 128, 128)    # teal
    >>> assert hsl_to_rgb(240, 1, 0.25) == (0, 0, 128)      # navy
    """
    if h == 360:
        h = 0
    assert 0 <= h < 360
    assert 0 <= s <= 1
    assert 0 <= l <= 1

    # calculate C, X, and m
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2

    rp: float
    gp: float
    bp: float

    # determine which sector of the hue circle the color is in
    match (h // 60) % 6:  # integer division and modulo for efficient sector mapping
        case 0:
            rp, gp, bp = c, x, 0.0
        case 1:
            rp, gp, bp = x, c, 0.0
        case 2:
            rp, gp, bp = 0.0, c, x
        case 3:
            rp, gp, bp = 0.0, x, c
        case 4:
            rp, gp, bp = x, 0.0, c
        case _:  # default case
            rp, gp, bp = c, 0.0, x

    # convert to 0-255 scale
    # note: round() instead of int() helps in precision. e.g. gray 127 -> 128
    return (round((rp + m) * 255), round((gp + m) * 255), round((bp + m) * 255))
