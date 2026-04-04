"""Flowchart data models for GMP document process flow diagrams."""

from dataclasses import dataclass, field


@dataclass
class FlowchartNode:
    id: str
    label: str
    shape: str  # rectangle, diamond, oval
    x: int = 0  # EMU position
    y: int = 0
    width: int = 0  # EMU size
    height: int = 0


@dataclass
class FlowchartConnector:
    from_node: str
    to_node: str
    label: str = ""


@dataclass
class Flowchart:
    nodes: list[FlowchartNode] = field(default_factory=list)
    connectors: list[FlowchartConnector] = field(default_factory=list)
    total_width: int = 0
    total_height: int = 0
