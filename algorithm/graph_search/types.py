from dataclasses import dataclass

@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    building_id: str | None = None
    name: str = ""
    criticality: str = "normal"

@dataclass(frozen=True)
class Edge:
    id: str
    start: str
    end: str
    kind: str
    weight: float = 1
    status: str = "normal"

@dataclass(frozen=True)
class Valve:
    id: str
    node: str
    status: str = "open"
