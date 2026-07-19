"""Shared category config for the TCG price-trend pipeline.

Top-10 TCGs by 2026 market relevance (client-selected). Categories launched
after the Feb 2024 archive start are indexed from their first sampled month.
"""

# categoryId -> (short display name, full name)
CATEGORIES = {
    1: ("Magic", "Magic: The Gathering"),
    3: ("Pokemon", "Pokemon"),
    2: ("Yu-Gi-Oh", "Yu-Gi-Oh!"),
    68: ("One Piece", "One Piece Card Game"),
    71: ("Lorcana", "Disney Lorcana"),
    89: ("Riftbound", "Riftbound: League of Legends TCG"),
    79: ("SW Unlimited", "Star Wars: Unlimited"),
    62: ("Flesh & Blood", "Flesh and Blood"),
    63: ("Digimon", "Digimon Card Game"),
    80: ("DBS Fusion World", "Dragon Ball Super: Fusion World"),
    77: ("Sorcery", "Sorcery: Contested Realm"),
    20: ("Weiss Schwarz", "Weiss Schwarz"),
}

# Panel/report order = the order above (market importance).
CATEGORY_ORDER = list(CATEGORIES)

# Realized TCGplayer GMV per game, USD over a ~3-month window ending Jul 2026
# (client-provided summary workbook, 2026-07; marketplace sales only).
# Used as static cross-game weights for the market composite.
GMV_3MO = {
    1: 65_061_147,    # Magic
    3: 52_355_898,    # Pokemon
    2: 11_646_389,    # Yu-Gi-Oh
    68: 20_719_110,   # One Piece
    71: 7_305_545,    # Lorcana
    79: 967_492,      # SW Unlimited
    62: 1_286_871,    # Flesh & Blood
    63: 1_833_381,    # Digimon
    80: 1_965_471,    # DBS Fusion World
    20: 683_482,      # Weiss Schwarz
    89: 6_947_506,    # Riftbound
    77: 888_295,      # Sorcery
}
