from pydantic import BaseModel, Field


class ResearchExplanation(BaseModel):
    summary: str

    key_findings: list[str] = Field(default_factory=list)

    risks: list[str] = Field(default_factory=list)

    limitations: list[str] = Field(default_factory=list)

    disclaimer: str = (
        "This research is informational, not financial advice. "
        "Returns are uncertain, and losses are possible."
    )