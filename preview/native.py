"""Five thin Copilot definitions. No native execution or workflow implementation."""
import shlex

DEFINITIONS = {
    "ordinary": ("domestique-v2-copilot", "Load the shared Domestique Copilot instructions."),
    "decompose": ("domestique-v2-copilot-decompose", "Load Domestique planning instructions without coding."),
    "goal": ("domestique-v2-copilot-goal", "Load an explicitly requested Domestique epic workflow."),
    "implementer": ("domestique-v2-copilot-implementer", "Implement one caller-assigned Domestique task."),
    "reviewer": ("domestique-v2-copilot-reviewer", "Independently review one caller-assigned Domestique task."),
}
ROLES = ("implementer", "reviewer")
LEAVES = {
    kind: (f".github/agents/{name}.agent.md" if kind in ROLES else
           f".github/skills/{name}/SKILL.md")
    for kind, (name, _) in DEFINITIONS.items()
}


def templates(launcher, project):
    result = {}
    for kind, (name, description) in DEFINITIONS.items():
        text = f"---\nname: {name}\ndescription: {description}\n"
        if kind == "goal":
            text += "disable-model-invocation: true\n"
        text += "---\n\n"
        command = shlex.join([str(launcher), "workflow", kind, "--project", str(project)])
        if kind in ROLES:
            text += (
                "Delegated role only: await the caller's explicit bounded task and retained\n"
                "shared-source instructions/context. Do not start a workflow, resolve the\n"
                "current revision independently, or run this locator autonomously.\n"
                "The caller's shared role-definition locator is:\n\n"
            )
        else:
            if kind == "goal":
                text += (
                    "Use only for an explicit Domestique goal request naming an epic.\n"
                    "Native goal/autopilot and ordinary planning are not authorization.\n\n"
                )
            text += (
                "Load instructions from the shared preview command for this explicit project;\n"
                "follow the returned instructions, not a copied local workflow engine:\n\n"
            )
        text += f"```sh\n{command}\n```\n\n"
        text += (
            "If loading fails, report that failure; do not invent a local fallback.\n"
            "Definition discovery alone does not establish operational workflow readiness.\n"
        )
        result[LEAVES[kind]] = text.encode()
    return result
