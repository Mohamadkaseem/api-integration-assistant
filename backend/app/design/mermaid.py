"""Builds a Mermaid flowchart from design steps (no AI).

Consecutive steps that each have a condition are drawn as branches of one
decision, e.g.  Search -> {decision} -> Update (if exists) / Create (if not) -> Log.
"""

from app.design.types import DesignStep

SHAPES = {
    "decide": ("{", "}"),
    "wait": ("([", "])"),
    "log": ("[/", "/]"),
}


def _label(text: str, limit: int = 80) -> str:
    text = " ".join(str(text).split())
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def build_mermaid(trigger: str, steps: list[DesignStep]) -> str:
    lines = ["flowchart TD"]
    lines.append(f'  T(["Trigger: {_label(trigger or "start")}"])')
    previous: list[str] = ["T"]          # nodes the next step connects from
    pending_label = ""                    # edge label (e.g. waits for ...)
    branch_anchor: str | None = None      # node that a group of conditional steps branches from
    branch_members: list[str] = []
    decision_count = 0

    def connect(sources: list[str], target: str, label: str = "") -> None:
        for src in sources:
            arrow = f' -->|"{_label(label, 50)}"| ' if label else " --> "
            lines.append(f"  {src}{arrow}{target}")

    for step in sorted(steps, key=lambda s: s.order):
        node = f"S{step.order}"
        open_, close = SHAPES.get(step.action, ("[", "]"))
        endpoint = f"<br/><small>{_label(step.endpoint_label, 60)}</small>" if step.endpoint_label else ""
        if step.match_status == "no_endpoint":
            endpoint = "<br/><small>⚠ no documented endpoint</small>"
        text = f"{_label(step.app or 'Step')}: {_label(step.description or step.action)}{endpoint}"
        lines.append(f'  {node}{open_}"{text}"{close}')
        if step.match_status == "no_endpoint":
            lines.append(f"  style {node} stroke:#d97706,stroke-width:2px,stroke-dasharray: 4 3")

        if step.condition:
            if branch_anchor is None:
                decision_count += 1
                branch_anchor = f"D{decision_count}"
                lines.append(f'  {branch_anchor}{{"Decision"}}')
                connect(previous, branch_anchor, pending_label)
                pending_label = ""
            connect([branch_anchor], node, step.condition)
            branch_members.append(node)
            continue

        label = step.waits_for and f"waits for: {step.waits_for}" or pending_label
        connect(branch_members or previous, node, label)
        branch_anchor, branch_members, pending_label = None, [], ""
        previous = [node]

    if branch_members:  # workflow ends with a decision
        previous = branch_members
    lines.append('  E(["Done"])')
    connect(previous, "E")
    return "\n".join(lines)
