"""Pydantic schemas for LLM-generated relationship arc templates.

These schemas define the structured output format for the relationship arc
generator when creating custom arc templates based on relationship dynamics.
"""

from pydantic import BaseModel, Field


class ArcPhaseTemplate(BaseModel):
    """Template for a single arc phase.

    Each phase represents a stage in the relationship arc's progression,
    with milestones to watch for and suggested dramatic scenes.
    """

    phase_key: str = Field(
        description="Unique identifier for this phase (lowercase, underscores, e.g., 'rising_tension', 'first_conflict')",
    )
    phase_name: str = Field(
        description="Human-readable name for the phase (e.g., 'Rising Tension', 'First Conflict')",
    )
    description: str = Field(
        description="Description of what happens during this phase (2-3 sentences)",
    )
    suggested_milestones: list[str] = Field(
        min_length=1,
        max_length=5,
        description="Key moments the GM should watch for during this phase (e.g., 'first_genuine_laugh', 'reveal_vulnerability')",
    )
    suggested_scenes: list[str] = Field(
        min_length=1,
        max_length=5,
        description="Dramatic scene ideas appropriate to this phase (e.g., 'Forced to work together against common enemy')",
    )
    typical_duration_description: str | None = Field(
        default=None,
        description="Rough guidance on phase duration (e.g., 'several encounters', 'one major event')",
    )


class GeneratedArcTemplate(BaseModel):
    """LLM-generated relationship arc template.

    Defines a complete narrative arc for a relationship between two characters,
    including phases, milestones, and possible endings. This template serves as
    GM guidance (inspiration, not script) - player actions always determine
    actual outcomes.
    """

    arc_type_name: str = Field(
        description="Unique name for this arc type (lowercase, underscores, e.g., 'forbidden_alliance', 'student_surpasses_master')",
    )
    arc_type_display: str = Field(
        description="Human-readable name (e.g., 'Forbidden Alliance', 'Student Surpasses Master')",
    )
    arc_description: str = Field(
        description="Overall description of what this arc represents (2-3 sentences)",
    )
    phases: list[ArcPhaseTemplate] = Field(
        min_length=3,
        max_length=6,
        description="Ordered phases of the arc (typically: introduction, development, crisis, climax, resolution)",
    )
    potential_endings: list[str] = Field(
        min_length=2,
        max_length=5,
        description="Possible ways this arc could resolve - include both positive and negative outcomes (player choice determines which)",
    )
    tension_triggers: list[str] = Field(
        min_length=2,
        max_length=5,
        description="Events or actions that would increase dramatic tension in this arc",
    )
    de_escalation_triggers: list[str] = Field(
        min_length=1,
        max_length=4,
        description="Events or actions that could defuse tension or redirect the arc",
    )
    setting_notes: str | None = Field(
        default=None,
        description="Setting-specific flavor or considerations for this arc",
    )
    why_this_arc: str = Field(
        description="Brief explanation of why this arc fits the current relationship dynamics",
    )
