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
    79: ("SW Unlimited", "Star Wars: Unlimited"),
    62: ("Flesh & Blood", "Flesh and Blood"),
    63: ("Digimon", "Digimon Card Game"),
    80: ("DBS Fusion World", "Dragon Ball Super: Fusion World"),
    20: ("Weiss Schwarz", "Weiss Schwarz"),
}

# Panel/report order = the order above (market importance).
CATEGORY_ORDER = list(CATEGORIES)
