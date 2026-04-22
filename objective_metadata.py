"""Objective variant metadata for room objectives."""

DEFAULT_ALTAR_VARIANT = "altar_anchor"
DEFAULT_RELIC_VARIANT = "relic_cache"


_ALTAR_VARIANTS = {
    DEFAULT_ALTAR_VARIANT: {
        "label": "Altar",
        "base_color": (210, 90, 220),
        "damaged_color": (150, 70, 170),
        "pulse_color": (245, 155, 255),
        "pulse_radius": 68,
        "pulse_damage": 4,
        "pulse_cycle_ms": 2400,
        "pulse_active_ms": 550,
        "pulse_stagger_ms": 180,
        "max_hp": 30,
    },
    "spore_totem": {
        "label": "Totem",
        "base_color": (112, 180, 86),
        "damaged_color": (78, 128, 62),
        "pulse_color": (170, 235, 120),
        "pulse_radius": 74,
        "pulse_damage": 4,
        "pulse_cycle_ms": 2200,
        "pulse_active_ms": 650,
        "pulse_stagger_ms": 220,
        "max_hp": 28,
    },
    "frost_obelisk": {
        "label": "Obelisk",
        "base_color": (138, 218, 255),
        "damaged_color": (86, 144, 182),
        "pulse_color": (214, 246, 255),
        "pulse_radius": 82,
        "pulse_damage": 5,
        "pulse_cycle_ms": 2600,
        "pulse_active_ms": 520,
        "pulse_stagger_ms": 260,
        "max_hp": 34,
    },
    "tidal_idol": {
        "label": "Idol",
        "base_color": (74, 164, 188),
        "damaged_color": (48, 102, 118),
        "pulse_color": (126, 222, 238),
        "pulse_radius": 78,
        "pulse_damage": 4,
        "pulse_cycle_ms": 2000,
        "pulse_active_ms": 720,
        "pulse_stagger_ms": 200,
        "max_hp": 32,
    },
}


_RELIC_VARIANTS = {
    DEFAULT_RELIC_VARIANT: {"label": "Relic"},
    "mire_cache": {"label": "Cache"},
    "glacier_reliquary": {"label": "Reliquary"},
    "sunken_sarcophagus": {"label": "Sarcophagus"},
}


def get_altar_variant(variant_id):
    return dict(_ALTAR_VARIANTS.get(variant_id, _ALTAR_VARIANTS[DEFAULT_ALTAR_VARIANT]))


def get_relic_variant(variant_id):
    return dict(_RELIC_VARIANTS.get(variant_id, _RELIC_VARIANTS[DEFAULT_RELIC_VARIANT]))


def pluralize_label(label):
    lower = label.lower()
    if lower.endswith("y") and len(label) > 1 and lower[-2] not in "aeiou":
        return f"{label[:-1]}ies"
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return f"{label}es"
    return f"{label}s"