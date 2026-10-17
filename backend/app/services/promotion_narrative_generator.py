import json
from dataclasses import dataclass
from typing import Any, Dict, List

from app.helpers.logging import logger
from app.services.ai_service import chat_completion
from app.services.promotion_engine import PlanEvaluation


SYSTEM_PROMPT = """You are a promotional marketing and operations advisor for a food & beverage retail business.
Generate clear, actionable promotional narratives based ONLY on the pre-computed financial and inventory inputs provided.

Rules:
- Write in clear, professional English.
- NEVER perform arithmetic or invent financial numbers. Use only the provided figures.
- Title must be engaging, concise (max 100 characters), and mention the promotion type or featured product(s).
- Rationale: Explain the strategic and commercial value of this promotion based on the numbers and context.
- Recommended actions: 3-5 concrete operational/marketing execution steps (e.g. staff briefing, POS setup, social media announcement, inventory staging).
- Risks: 1-3 practical risks or trade-offs (e.g., stockouts, kitchen bottlenecks, margin erosion, cannibalization).
- Output MUST be a valid JSON object matching the exact schema below. No text outside the JSON."""

RESPONSE_SCHEMA = """\
Respond with a JSON object with exactly these fields:
{
  "title": "catchy and descriptive promotion title (max 100 chars)",
  "rationale": "strategic justification referencing provided figures",
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "risks": ["risk 1", "risk 2"]
}"""


@dataclass
class PromotionNarrativeResult:
    title: str
    rationale: str
    recommended_actions: List[str]
    risks: List[str]


def build_promotion_prompt(
    promotion_type: str,
    start_date: str,
    end_date: str,
    evaluation: PlanEvaluation,
) -> str:
    prompt_data = {
        "promotion_type": promotion_type,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "is_financially_validated": evaluation.is_financially_validated,
        "total_original_revenue": str(evaluation.total_original_revenue) if evaluation.total_original_revenue is not None else None,
        "total_discounted_revenue": str(evaluation.total_discounted_revenue) if evaluation.total_discounted_revenue is not None else None,
        "total_estimated_cost": str(evaluation.total_estimated_cost) if evaluation.total_estimated_cost is not None else None,
        "total_estimated_margin": str(evaluation.total_estimated_margin) if evaluation.total_estimated_margin is not None else None,
        "avg_margin_pct": str(evaluation.avg_margin_pct) if evaluation.avg_margin_pct is not None else None,
        "items": [
            {
                "product_id": it.product_id,
                "product_name": it.product_name,
                "discount_type": it.discount_type,
                "discount_value": str(it.discount_value),
                "original_price": str(it.original_price) if it.original_price is not None else None,
                "discounted_price": str(it.discounted_price) if it.discounted_price is not None else None,
                "margin_pct": str(it.margin_pct) if it.margin_pct is not None else None,
                "expected_qty": it.expected_qty,
                "cost_data_available": it.cost_data_available,
            }
            for it in evaluation.items
        ],
        "warnings": evaluation.warnings,
        "missing_data": evaluation.missing_data,
        "risks": evaluation.risks,
    }
    return (
        f"Generate promotional narrative fields for this promotion plan:\n"
        f"{json.dumps(prompt_data, ensure_ascii=False, indent=2)}\n\n"
        f"{RESPONSE_SCHEMA}"
    )


class PromotionNarrativeGenerator:
    """
    Generates dynamic AI narratives for deterministic PlanEvaluation.
    Strictly English output, no silent fallback templates.
    """

    async def generate_narrative(
        self,
        promotion_type: str,
        start_date: Any,
        end_date: Any,
        evaluation: PlanEvaluation,
    ) -> PromotionNarrativeResult:
        """Call AI service and parse structured JSON response."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_promotion_prompt(promotion_type, str(start_date), str(end_date), evaluation)},
        ]

        logger.info(
            f"Generating AI promotion narrative for type={promotion_type}, "
            f"items_count={len(evaluation.items)}"
        )

        response = await chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )

        content = response["choices"][0]["message"]["content"]
        parsed = self._parse_ai_response(content)

        return PromotionNarrativeResult(
            title=str(parsed["title"]).strip()[:255],
            rationale=str(parsed["rationale"]).strip(),
            recommended_actions=[str(s).strip() for s in parsed["recommended_actions"]],
            risks=[str(r).strip() for r in parsed["risks"]],
        )

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
            "recommended_actions",
            "risks",
        ]
        missing = [f for f in required if f not in parsed]
        if missing:
            raise ValueError(f"AI response missing required fields: {missing}")

        for list_field in ("recommended_actions", "risks"):
            if not isinstance(parsed[list_field], list):
                raise ValueError(
                    f"AI response field '{list_field}' must be a list, got {type(parsed[list_field]).__name__}"
                )

        return parsed
