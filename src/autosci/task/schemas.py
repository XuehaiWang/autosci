"""Task understanding schemas — structured output of the TaskUnderstandingAgent.

Replaces the old simple TaskPlan with a richer structure:
  - TaskContext: parsed from the task description (Context Parsing)
  - RelatedWork: extracted from each paper (Contribution Extraction)
  - Claim: a verifiable hypothesis with supporting rationale
  - ResearchQuestion: derived from context + related work gap
  - TaskPlan: the complete understanding artifact
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Context Parsing ────────────────────────────────────────────────────────────

@dataclass
class TaskContext:
    """Structured parse of the research task description."""

    research_subject: str = ""       # 研究对象
    data_type: str = ""              # 数据类型/实验材料
    task_goal: str = ""              # 任务目标
    known_methods: list[str] = field(default_factory=list)  # 已知方法/baseline
    key_terms: list[str] = field(default_factory=list)       # 核心关键词（用于文献检索）

    def to_dict(self) -> dict:
        return {
            "research_subject": self.research_subject,
            "data_type": self.data_type,
            "task_goal": self.task_goal,
            "known_methods": self.known_methods,
            "key_terms": self.key_terms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TaskContext":
        return cls(
            research_subject=d.get("research_subject", ""),
            data_type=d.get("data_type", ""),
            task_goal=d.get("task_goal", ""),
            known_methods=d.get("known_methods", []),
            key_terms=d.get("key_terms", []),
        )


# ── Contribution Extraction ────────────────────────────────────────────────────

@dataclass
class RelatedWork:
    """Key information extracted from one related paper."""

    title: str
    source: str                     # URL or file path
    contribution: str               # core contribution (1-2 sentences)
    evidence: str                   # what experiment/data supports it
    boundary: str                   # limitation / future direction / gap
    year: str = ""
    authors: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "contribution": self.contribution,
            "evidence": self.evidence,
            "boundary": self.boundary,
            "year": self.year,
            "authors": self.authors,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RelatedWork":
        return cls(
            title=d.get("title", ""),
            source=d.get("source", ""),
            contribution=d.get("contribution", ""),
            evidence=d.get("evidence", ""),
            boundary=d.get("boundary", ""),
            year=d.get("year", ""),
            authors=d.get("authors", ""),
        )


# ── Research Questions & Claims ────────────────────────────────────────────────

@dataclass
class ResearchQuestion:
    """A specific, answerable question derived from context + literature gap."""

    id: str
    question: str
    motivation: str                 # 为什么这个问题值得问（源自哪个 gap）
    related_work_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "motivation": self.motivation,
            "related_work_ids": self.related_work_ids,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchQuestion":
        return cls(
            id=d.get("id", ""),
            question=d.get("question", ""),
            motivation=d.get("motivation", ""),
            related_work_ids=d.get("related_work_ids", []),
        )


@dataclass
class Claim:
    """A verifiable hypothesis — the core testable proposition of the research."""

    id: str
    statement: str                  # 具体命题
    type: str                       # comparative | existence | improvement | causal
    verifiable_by: str              # 用什么实验/数据可以验证
    related_rq_id: str = ""         # 对应哪个 ResearchQuestion
    status: str = "unverified"      # unverified | supported | refuted | partial

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "statement": self.statement,
            "type": self.type,
            "verifiable_by": self.verifiable_by,
            "related_rq_id": self.related_rq_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        return cls(
            id=d.get("id", ""),
            statement=d.get("statement", ""),
            type=d.get("type", ""),
            verifiable_by=d.get("verifiable_by", ""),
            related_rq_id=d.get("related_rq_id", ""),
            status=d.get("status", "unverified"),
        )


# ── TaskPlan (complete understanding artifact) ────────────────────────────────

@dataclass
class TaskPlan:
    """Complete structured understanding of a research task.

    Produced by TaskUnderstandingAgent and consumed by:
    - MainAgent (injected as system prompt context)
    - WorkflowEngine (claims guide phase goals)
    - TrajectoryRecorder (saved as task_plan event)
    """

    raw_task: str
    mode: str                           # "topic_only" | "task_given"
    goal: str                           # one-sentence core objective
    context: Optional[TaskContext] = None
    related_works: list[RelatedWork] = field(default_factory=list)
    research_questions: list[ResearchQuestion] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    suggested_agents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "raw_task": self.raw_task,
            "mode": self.mode,
            "goal": self.goal,
            "context": self.context.to_dict() if self.context else {},
            "related_works": [r.to_dict() for r in self.related_works],
            "research_questions": [rq.to_dict() for rq in self.research_questions],
            "claims": [c.to_dict() for c in self.claims],
            "suggested_agents": self.suggested_agents,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TaskPlan":
        return cls(
            raw_task=d.get("raw_task", ""),
            mode=d.get("mode", "task_given"),
            goal=d.get("goal", ""),
            context=TaskContext.from_dict(d["context"]) if d.get("context") else None,
            related_works=[RelatedWork.from_dict(r) for r in d.get("related_works", [])],
            research_questions=[ResearchQuestion.from_dict(rq) for rq in d.get("research_questions", [])],
            claims=[Claim.from_dict(c) for c in d.get("claims", [])],
            suggested_agents=d.get("suggested_agents", []),
        )

    @classmethod
    def fallback(cls, task: str) -> "TaskPlan":
        """Minimal plan when understanding fails."""
        return cls(raw_task=task, mode="task_given", goal=task[:200])

    def to_prompt_block(self) -> str:
        """Format for injection into the main agent's system prompt."""
        lines = ["## Task Understanding\n"]
        lines.append(f"**Goal**: {self.goal}\n")

        if self.context:
            ctx = self.context
            lines.append("**Context**:")
            if ctx.research_subject:
                lines.append(f"  - Research subject: {ctx.research_subject}")
            if ctx.data_type:
                lines.append(f"  - Data/materials: {ctx.data_type}")
            if ctx.task_goal:
                lines.append(f"  - Task objective: {ctx.task_goal}")
            if ctx.known_methods:
                lines.append(f"  - Known methods: {', '.join(ctx.known_methods)}")
            lines.append("")

        if self.research_questions:
            lines.append("**Research Questions**:")
            for rq in self.research_questions:
                lines.append(f"  [{rq.id}] {rq.question}")
            lines.append("")

        if self.claims:
            lines.append("**Claims to verify** (currently unverified hypotheses):")
            for c in self.claims:
                lines.append(f"  [{c.id}] {c.statement}")
                lines.append(f"        → Verify by: {c.verifiable_by}")
            lines.append("")

        if self.related_works:
            lines.append(f"**Related work surveyed**: {len(self.related_works)} papers")
            for rw in self.related_works[:5]:  # show top 5 in prompt
                lines.append(f"  - {rw.title}: {rw.contribution[:100]}")
                if rw.boundary:
                    lines.append(f"    Gap: {rw.boundary[:100]}")
            lines.append("")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Full human-readable report for workspace/task_understanding.md."""
        lines = [
            f"# Task Understanding Report\n",
            f"**Mode**: {self.mode}",
            f"**Goal**: {self.goal}\n",
            "---\n",
        ]

        if self.context:
            ctx = self.context
            lines.append("## Context Parsing\n")
            lines.append(f"| Dimension | Content |")
            lines.append(f"|-----------|---------|")
            lines.append(f"| Research subject | {ctx.research_subject} |")
            lines.append(f"| Data/materials | {ctx.data_type} |")
            lines.append(f"| Task objective | {ctx.task_goal} |")
            lines.append(f"| Known methods | {', '.join(ctx.known_methods) or '—'} |")
            lines.append(f"| Key terms | {', '.join(ctx.key_terms) or '—'} |\n")

        if self.related_works:
            lines.append("## Related Work\n")
            for i, rw in enumerate(self.related_works, 1):
                lines.append(f"### {i}. {rw.title}")
                if rw.authors or rw.year:
                    lines.append(f"*{rw.authors} ({rw.year})*  ")
                lines.append(f"Source: {rw.source}\n")
                lines.append(f"**Contribution**: {rw.contribution}\n")
                lines.append(f"**Evidence**: {rw.evidence}\n")
                lines.append(f"**Gap / Boundary**: {rw.boundary}\n")

        if self.research_questions:
            lines.append("## Research Questions\n")
            for rq in self.research_questions:
                lines.append(f"**[{rq.id}]** {rq.question}\n")
                lines.append(f"> Motivation: {rq.motivation}\n")

        if self.claims:
            lines.append("## Claims (Hypotheses)\n")
            lines.append("| ID | Statement | Type | Verify by | Status |")
            lines.append("|----|-----------|------|-----------|--------|")
            for c in self.claims:
                lines.append(
                    f"| {c.id} | {c.statement} | {c.type} | {c.verifiable_by} | {c.status} |"
                )
            lines.append("")

        return "\n".join(lines)


# ── Persistence ────────────────────────────────────────────────────────────────

def save_task_plan(plan: TaskPlan, workspace: str) -> str:
    """Save to {workspace}/task_plan.json. Returns path."""
    path = os.path.join(workspace, "task_plan.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)
    return path


def save_task_understanding_report(plan: TaskPlan, workspace: str) -> str:
    """Save full Markdown report to {workspace}/task_understanding.md."""
    path = os.path.join(workspace, "task_understanding.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(plan.to_markdown())
    return path


def load_task_plan(workspace: str) -> Optional[TaskPlan]:
    """Load task plan from {workspace}/task_plan.json."""
    path = os.path.join(workspace, "task_plan.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return TaskPlan.from_dict(json.load(f))
    except Exception as e:
        logger.warning(f"Failed to load task plan: {e}")
        return None
