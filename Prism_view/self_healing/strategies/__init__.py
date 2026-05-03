"""PRISM self-healing strategies — ordered priority pipeline."""
from Prism_view.self_healing.strategies.base import HealingStrategy, HealCandidate
from Prism_view.self_healing.strategies.id_strategy import IdStrategy
from Prism_view.self_healing.strategies.name_strategy import NameStrategy
from Prism_view.self_healing.strategies.aria_strategy import AriaStrategy
from Prism_view.self_healing.strategies.class_strategy import ClassStrategy
from Prism_view.self_healing.strategies.dom_neighbour_strategy import DomNeighbourStrategy
from Prism_view.self_healing.strategies.registry_strategy import RegistryStrategy

# Default ordered pipeline (matches user's approved priority order)
DEFAULT_PIPELINE = [
    IdStrategy,            # 1. Exact id match
    NameStrategy,          # 2. Exact name match
    AriaStrategy,          # 3. aria-label / placeholder similarity
    ClassStrategy,         # 4. CSS class similarity
    DomNeighbourStrategy,  # 5. DOM neighbour / structural position
    RegistryStrategy,      # 6. Historical locator registry lookup
]

__all__ = [
    "HealingStrategy", "HealCandidate", "DEFAULT_PIPELINE",
    "IdStrategy", "NameStrategy", "AriaStrategy",
    "ClassStrategy", "DomNeighbourStrategy", "RegistryStrategy",
]
