"""ASTRA-v2 self-healing strategies — ordered priority pipeline."""
from Asearch.self_healing.strategies.base import HealingStrategy, HealCandidate
from Asearch.self_healing.strategies.id_strategy import IdStrategy
from Asearch.self_healing.strategies.name_strategy import NameStrategy
from Asearch.self_healing.strategies.aria_strategy import AriaStrategy
from Asearch.self_healing.strategies.class_strategy import ClassStrategy
from Asearch.self_healing.strategies.dom_neighbour_strategy import DomNeighbourStrategy
from Asearch.self_healing.strategies.registry_strategy import RegistryStrategy

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
