from __future__ import annotations

from collections.abc import Callable
from os import getenv
from uuid import uuid4

from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import MODEL, root_agent
from .models import AgentBrief, EvidenceCaseResult


class AdkBriefService:
    """Run the Google ADK fleet on a persisted, redacted case result."""

    def __init__(
        self, runner_factory: Callable[[], InMemoryRunner] | None = None
    ) -> None:
        self._runner_factory = runner_factory or (
            lambda: InMemoryRunner(node=root_agent, app_name="evidenceops_fleet")
        )

    async def generate(self, result: EvidenceCaseResult) -> AgentBrief:
        vertex_enabled = getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
        if not getenv("GOOGLE_API_KEY") and not vertex_enabled:
            raise RuntimeError("Gemini credentials are not configured")

        runner = self._runner_factory()
        user_id = "case-reviewer"
        session_id = f"case-{uuid4()}"
        await runner.session_service.create_session(
            app_name="evidenceops_fleet", user_id=user_id, session_id=session_id
        )
        redacted_json = result.model_dump_json()
        message = types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=(
                        "Generate an evidence-bound action brief from this persisted "
                        "result JSON. This brief is advisory and cannot change its "
                        f"decision. Never infer missing facts:\n{redacted_json}"
                    )
                )
            ],
        )
        final_text = ""
        final_author = ""
        event_count = 0
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=message
        ):
            event_count += 1
            if event.is_final_response() and event.content:
                text_parts = [part.text for part in event.content.parts or [] if part.text]
                if text_parts:
                    final_text = "\n".join(text_parts)
                    final_author = event.author
        if not final_text:
            raise RuntimeError("ADK fleet returned no final brief")
        return AgentBrief(
            case_id=result.case_id,
            source_decision=result.decision,
            source_evidence_digest=result.evidence_digest,
            model=MODEL,
            brief=final_text,
            final_author=final_author,
            event_count=event_count,
        )
