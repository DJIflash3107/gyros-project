import asyncio
import json
from typing import Any, Dict, List, Optional

from app.helpers.logging import logger
from app.services.ai_service import chat_completion
from app.services.business_action_engine import ActionCandidate


SYSTEM_PROMPT = """You are a business operations advisor for a food & beverage business.
Generate actionable recommendations based ONLY on the provided data.

Rules:
- Write in clear, professional English.
- Reference specific numbers from the provided supporting_data. NEVER invent statistics.
- Clearly distinguish measured facts (evidence_quality: "measured") from estimates/projections (evidence_quality: "estimated").
- Title must be concise (max 80 characters), descriptive, and mention the product/branch if relevant.
- Recommended steps must be specific and actionable (3-5 steps).
- Risks: 1-3 concrete trade-offs or downsides.
- Success metrics: 1-3 measurable targets with timeframes.
- Limitations: explain data quality caveats honestly.
- Output MUST be a valid JSON object matching the exact schema below. No text outside the JSON."""

RESPONSE_SCHEMA = """\
Respond with a JSON object with exactly these fields:
{
  "title": "short actionable title (max 80 chars)",
  "rationale": "why this action matters, reference specific numbers",
  "recommended_steps": ["step 1", "step 2", "step 3"],
  "risks": ["risk 1"],
  "success_metrics": ["measurable metric 1"],
  "limitations": "data quality caveats"
}"""


def build_candidate_prompt(candidate: ActionCandidate) -> str:
    """Build the prompt for an individual ActionCandidate."""
    prompt_data = {
        "action_type": candidate.action_type,
        "rule_label": candidate.rule_label,
        "category": candidate.category,
        "urgency": candidate.urgency,
        "expected_impact": candidate.expected_impact,
        "evidence_quality": candidate.evidence_quality,
        "supporting_data": candidate.supporting_data,
    }
    return (
        f"Generate narrative fields for this business recommendation:\n"
        f"{json.dumps(prompt_data, ensure_ascii=False, indent=2)}\n\n"
        f"{RESPONSE_SCHEMA}"
    )


class ActionNarrativeGenerator:
    """
    Generates dynamic AI narratives for deterministic ActionCandidates.
    Strictly English output, no silent fallback templates.
    """

    MAX_CONCURRENT = 5

    async def enrich_candidates(
        self, candidates: List[ActionCandidate]
    ) -> List[ActionCandidate]:
        """
        Enrich all candidates with AI-generated narratives concurrently.
        Raises on AI failure — no silent fallback.
        """
        if not candidates:
            return candidates

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)

        async def _enrich_one(candidate: ActionCandidate) -> ActionCandidate:
            async with semaphore:
                return await self._generate_narrative(candidate)

        results = await asyncio.gather(*[_enrich_one(c) for c in candidates])
        return list(results)

    async def _generate_narrative(self, candidate: ActionCandidate) -> ActionCandidate:
        """Call AI service and parse structured JSON response."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_candidate_prompt(candidate)},
        ]

        logger.info(
            f"Generating AI narrative for action_type={candidate.action_type}, "
            f"rule_label={candidate.rule_label}"
        )

        response = await chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )

        content = response["choices"][0]["message"]["content"]
        parsed = self._parse_ai_response(content)

        candidate.title = str(parsed["title"]).strip()[:120]
        candidate.rationale = str(parsed["rationale"]).strip()
        candidate.recommended_steps = [str(s).strip() for s in parsed["recommended_steps"]]
        candidate.risks = [str(r).strip() for r in parsed["risks"]]
        candidate.success_metrics = [str(m).strip() for m in parsed["success_metrics"]]
        candidate.limitations = str(parsed["limitations"]).strip()
        candidate.ai_generated = True

        return candidate

    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from AI response, stripping markdown fences if present."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError(f"AI response must be a JSON object, got {type(parsed).__name__}")

        required = [
            "title",
            "rationale",
            "recommended_steps",
            "risks",
            "success_metrics",
            "limitations",
        ]
        missing = [f for f in required if f not in parsed]
        if missing:
            raise ValueError(f"AI response missing required fields: {missing}")

        for list_field in ("recommended_steps", "risks", "success_metrics"):
            if not isinstance(parsed[list_field], list):
                raise ValueError(
                    f"AI response field '{list_field}' must be a list, got {type(parsed[list_field]).__name__}"
                )

        return parsed
