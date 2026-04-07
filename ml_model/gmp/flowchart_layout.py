"""Auto-layout engine for flowchart positioning.

Takes a list of process steps with connections and computes
node positions in EMU for OOXML embedding.
"""

from .flowchart import Flowchart, FlowchartNode, FlowchartConnector
from .ooxml_helpers import EMU_PER_INCH

# Layout constants (in EMU)
NODE_WIDTH = int(2.0 * EMU_PER_INCH)       # 2 inches
NODE_HEIGHT = int(0.6 * EMU_PER_INCH)      # 0.6 inches
DECISION_WIDTH = int(2.2 * EMU_PER_INCH)   # 2.2 inches
DECISION_HEIGHT = int(1.2 * EMU_PER_INCH)  # 1.2 inches
OVAL_WIDTH = int(1.8 * EMU_PER_INCH)
OVAL_HEIGHT = int(0.5 * EMU_PER_INCH)
V_GAP = int(0.5 * EMU_PER_INCH)            # Vertical gap between nodes
H_GAP = int(1.5 * EMU_PER_INCH)            # Horizontal gap for branches
PADDING = int(0.3 * EMU_PER_INCH)          # Canvas padding


class FlowchartLayoutEngine:
    """Computes positions for flowchart nodes using a top-down layout."""

    def layout(self, steps: list[dict]) -> Flowchart:
        """Compute layout from LLM-generated step definitions.

        Args:
            steps: List of dicts with keys:
                - id: str
                - label: str
                - type: 'start' | 'action' | 'decision' | 'end'
                - next: list of {target_id, label?}

        Returns:
            Flowchart with positioned nodes and connectors
        """
        if not steps:
            return Flowchart()

        # Build step lookup
        step_map = {s["id"]: s for s in steps}

        # Determine shape and size for each node
        nodes = []
        for step in steps:
            shape, width, height = self._get_shape_params(step["type"])
            nodes.append(FlowchartNode(
                id=step["id"],
                label=step["label"],
                shape=shape,
                width=width,
                height=height,
            ))

        node_map = {n.id: n for n in nodes}

        # Simple top-down layout with branch detection
        # Main column is centered; decision branches go to the right
        visited = set()
        col_x = PADDING
        y = PADDING

        # Walk the main path
        main_path = self._find_main_path(steps, step_map)
        branch_nodes = []

        for step_id in main_path:
            if step_id not in node_map:
                continue
            node = node_map[step_id]
            node.x = col_x + (NODE_WIDTH - node.width) // 2
            node.y = y
            y += node.height + V_GAP
            visited.add(step_id)

            # Check for branch targets (decision "No" path)
            step = step_map.get(step_id)
            if step and step["type"] == "decision" and len(step.get("next", [])) > 1:
                # Second target is the branch
                branch_target = step["next"][1].get("target_id")
                if branch_target and branch_target not in visited:
                    branch_nodes.append((branch_target, node.y))

        # Layout branch nodes to the right
        branch_x = col_x + NODE_WIDTH + H_GAP
        for branch_id, branch_y in branch_nodes:
            if branch_id in node_map and branch_id not in visited:
                node = node_map[branch_id]
                node.x = branch_x + (NODE_WIDTH - node.width) // 2
                node.y = branch_y + V_GAP
                visited.add(branch_id)

        # Build connectors
        connectors = []
        for step in steps:
            for next_info in step.get("next", []):
                target_id = next_info.get("target_id")
                if target_id and target_id in node_map:
                    connectors.append(FlowchartConnector(
                        from_node=step["id"],
                        to_node=target_id,
                        label=next_info.get("label", ""),
                    ))

        # Calculate total canvas size
        max_x = max((n.x + n.width for n in nodes if n.x > 0), default=NODE_WIDTH)
        max_y = max((n.y + n.height for n in nodes if n.y > 0), default=NODE_HEIGHT)

        return Flowchart(
            nodes=nodes,
            connectors=connectors,
            total_width=max_x + PADDING,
            total_height=max_y + PADDING,
        )

    def _get_shape_params(self, node_type: str) -> tuple[str, int, int]:
        """Get shape name and dimensions for a node type."""
        if node_type == "decision":
            return "diamond", DECISION_WIDTH, DECISION_HEIGHT
        elif node_type in ("start", "end"):
            return "oval", OVAL_WIDTH, OVAL_HEIGHT
        else:
            return "rectangle", NODE_WIDTH, NODE_HEIGHT

    def _find_main_path(self, steps: list[dict], step_map: dict) -> list[str]:
        """Find the main (longest) path through the flowchart.

        Follows the first next target at each step (typically the "Yes" path
        for decisions).
        """
        if not steps:
            return []

        path = []
        visited = set()
        current = steps[0]["id"]

        while current and current not in visited:
            path.append(current)
            visited.add(current)
            step = step_map.get(current)
            if not step or not step.get("next"):
                break
            # Follow first (main) path
            current = step["next"][0].get("target_id")

        return path
