"""
crew.py
=======
Builds the CrewAI Agent/Task/Crew objects from the jsonc config files.
This is the "wiring" layer: it does NOT contain any RAG logic itself —
it just resolves "custom:doc_search" -> DocumentRAGTool() and hands
everything to CrewAI.
"""

import os
import re
import json

from dotenv import load_dotenv
load_dotenv(override=True)  # reads .env in the project root and populates os.environ

try:
    from crewai import Agent, Task, Crew, Process, LLM
except ImportError:
    # Fallback for environments where the package is named differently
    try:
        from crew_ai import Agent, Task, Crew, Process, LLM  # type: ignore
    except ImportError:
        raise ImportError(
            "Could not import 'crewai' or 'crew_ai'. Install the CrewAI package or adjust PYTHONPATH."
        )

from tools.rag_tool import DocumentRAGTool

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")


def load_jsonc(path: str) -> dict:
    """Minimal JSONC loader: strip // line-comments, then json.loads()."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    # Strip // comments that are not inside a string (simple heuristic:
    # our config files never use // inside string values, so a plain
    # line-based strip is safe here).
    lines = []
    for line in raw.splitlines():
        stripped = line
        # remove a trailing // comment (only if // isn't inside quotes)
        if "//" in line and not re.search(r'"[^"]*//[^"]*"', line):
            stripped = re.sub(r'\s*//.*$', '', line)
        lines.append(stripped)
    cleaned = "\n".join(lines)
    return json.loads(cleaned)


def get_llm() -> LLM:
    """Supports either OpenRouter (.env: MODEL + OPENROUTER_API_KEY)
    or direct Anthropic (.env: ANTHROPIC_API_KEY) — whichever is set."""
    or_key = os.environ.get("OPENROUTER_API_KEY")
    or_model = os.environ.get("MODEL")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if or_key and or_model:
        return LLM(
            model=f"openrouter/{or_model}",
            api_key=or_key,
            temperature=0.2,
        )
    elif anthropic_key:
        return LLM(
            model="anthropic/claude-sonnet-4-5-20250929",
            api_key=anthropic_key,
            temperature=0.2,
        )
    else:
        raise RuntimeError(
            "No LLM credentials found in .env. Set either:\n"
            "  OPENROUTER_API_KEY + MODEL   (for OpenRouter)\n"
            "  ANTHROPIC_API_KEY            (for direct Anthropic)"
        )


def build_crew(question: str) -> Crew:
    agents_cfg = load_jsonc(os.path.join(CONFIG_DIR, "agents.jsonc"))
    tasks_cfg = load_jsonc(os.path.join(CONFIG_DIR, "tasks.jsonc"))

    llm = get_llm()

    # One shared tool instance -> index is built ONCE (chunk+embed),
    # reused by every agent/task/run instead of re-indexing every time.
    doc_search_tool = DocumentRAGTool()

    TOOL_REGISTRY = {
        "custom:doc_search": doc_search_tool,
    }

    # ---- build agents ----
    agents = {}
    for key, cfg in agents_cfg.items():
        resolved_tools = [TOOL_REGISTRY[t] for t in cfg.get("tools", [])]
        agents[key] = Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=resolved_tools,
            allow_delegation=cfg.get("allow_delegation", False),
            verbose=cfg.get("verbose", True),
            llm=llm,
        )

    # ---- build tasks (in file order, so context references resolve) ----
    tasks = {}
    for key, cfg in tasks_cfg.items():
        description = cfg["description"].format(question=question)
        context_tasks = [tasks[c] for c in cfg.get("context", [])]

        task_kwargs = dict(
            description=description,
            expected_output=cfg["expected_output"],
            agent=agents[cfg["agent"]],
            context=context_tasks if context_tasks else None,
        )
        if "output_file" in cfg:
            task_kwargs["output_file"] = cfg["output_file"]

        tasks[key] = Task(**task_kwargs)

    crew = Crew(
        agents=list(agents.values()),
        tasks=list(tasks.values()),
        process=Process.sequential,
        verbose=True,
    )
    return crew