import asyncio
from decimal import Decimal
import json
from unittest.mock import AsyncMock, patch
import pytest

from app.helpers.exceptions import AIServiceException, AIRateLimitException
from app.services.action_narrative_generator import (
    ActionNarrativeGenerator,
    build_candidate_prompt,
    SYSTEM_PROMPT,
)
from app.services.business_action_engine import ActionCandidate


def _make_candidate(action_type="INV-001", rule_label="high_spoilage"):
    return ActionCandidate(
        action_type=action_type,
        category="inventory",
        rule_label=rule_label,
        urgency="high",
        expected_impact="high",
        priority_score=Decimal("80.00"),
        evidence_quality="measured",
        supporting_data={
            "spoilage_rate": 0.25,
            "total_spoiled": 20,
            "context": {
                "product_name": "Greek Salad",
                "branch_name": "Central Hub",
                "days_in_period": 30,
                "business_name": "Gyros Master",
            },
        },
        branch_id=1,
        product_id=10,
    )


@pytest.mark.asyncio
async def test_enrich_candidates_success():
    generator = ActionNarrativeGenerator()
    candidate = _make_candidate()

    mock_ai_payload = {
        "title": "Address High Spoilage for Greek Salad",
        "rationale": "Greek Salad has a 25% spoilage rate with 20 spoiled units in Central Hub.",
        "recommended_steps": [
            "Inspect cold storage temperatures daily",
            "Adjust prep batch sizes downward by 20%",
            "Implement strict FIFO inventory rotation",
        ],
        "risks": ["Under-preparing may risk stockouts during lunch peaks"],
        "success_metrics": ["Reduce spoilage rate below 10% within 14 days"],
        "limitations": "Based strictly on submitted daily sales reports.",
    }

    mock_chat_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": json.dumps(mock_ai_payload)}}]}
    )

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        enriched = await generator.enrich_candidates([candidate])

    assert len(enriched) == 1
    c = enriched[0]
    assert c.title == "Address High Spoilage for Greek Salad"
    assert c.rationale == "Greek Salad has a 25% spoilage rate with 20 spoiled units in Central Hub."
    assert len(c.recommended_steps) == 3
    assert len(c.risks) == 1
    assert len(c.success_metrics) == 1
    assert "submitted daily sales reports" in c.limitations
    assert c.ai_generated is True
    assert c.rule_label == "high_spoilage"
    assert c.priority_score == Decimal("80.00")


@pytest.mark.asyncio
async def test_enrich_candidates_strips_markdown_code_fences():
    generator = ActionNarrativeGenerator()
    candidate = _make_candidate()

    raw_json = json.dumps({
        "title": "Clean Title Without Markdown",
        "rationale": "Sample rationale referencing facts.",
        "recommended_steps": ["Step 1", "Step 2", "Step 3"],
        "risks": ["Risk 1"],
        "success_metrics": ["Metric 1"],
        "limitations": "Data limitations disclaimer",
    })
    fenced_content = f"```json\n{raw_json}\n```"

    mock_chat_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": fenced_content}}]}
    )

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        enriched = await generator.enrich_candidates([candidate])

    assert enriched[0].title == "Clean Title Without Markdown"


@pytest.mark.asyncio
async def test_enrich_candidates_truncates_title_at_120_chars():
    generator = ActionNarrativeGenerator()
    candidate = _make_candidate()

    super_long_title = "A" * 150
    mock_ai_payload = {
        "title": super_long_title,
        "rationale": "Rationale",
        "recommended_steps": ["Step 1"],
        "risks": ["Risk 1"],
        "success_metrics": ["Metric 1"],
        "limitations": "Limitations",
    }

    mock_chat_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": json.dumps(mock_ai_payload)}}]}
    )

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        enriched = await generator.enrich_candidates([candidate])

    assert len(enriched[0].title) == 120
    assert enriched[0].title == "A" * 120


@pytest.mark.asyncio
async def test_enrich_empty_candidates_returns_empty_without_ai_call():
    generator = ActionNarrativeGenerator()
    mock_chat_completion = AsyncMock()

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        result = await generator.enrich_candidates([])

    assert result == []
    mock_chat_completion.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_propagates_ai_service_exception():
    generator = ActionNarrativeGenerator()
    candidate = _make_candidate()

    mock_chat_completion = AsyncMock(
        side_effect=AIServiceException(status_code=504, message="AI gateway timeout")
    )

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        with pytest.raises(AIServiceException) as exc_info:
            await generator.enrich_candidates([candidate])

    assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_enrich_propagates_rate_limit_exception():
    generator = ActionNarrativeGenerator()
    candidate = _make_candidate()

    mock_chat_completion = AsyncMock(side_effect=AIRateLimitException("Rate limit exceeded"))

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        with pytest.raises(AIRateLimitException):
            await generator.enrich_candidates([candidate])


@pytest.mark.asyncio
async def test_enrich_raises_on_malformed_json():
    generator = ActionNarrativeGenerator()
    candidate = _make_candidate()

    mock_chat_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": "This is plain text, not JSON"}}]}
    )

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        with pytest.raises(json.JSONDecodeError):
            await generator.enrich_candidates([candidate])


@pytest.mark.asyncio
async def test_enrich_raises_on_missing_required_field():
    generator = ActionNarrativeGenerator()
    candidate = _make_candidate()

    # Missing 'limitations'
    incomplete_payload = {
        "title": "Title",
        "rationale": "Rationale",
        "recommended_steps": ["Step 1"],
        "risks": ["Risk 1"],
        "success_metrics": ["Metric 1"],
    }

    mock_chat_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": json.dumps(incomplete_payload)}}]}
    )

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        with pytest.raises(ValueError) as exc_info:
            await generator.enrich_candidates([candidate])

    assert "missing required fields" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_enrich_raises_when_steps_is_not_a_list():
    generator = ActionNarrativeGenerator()
    candidate = _make_candidate()

    invalid_payload = {
        "title": "Title",
        "rationale": "Rationale",
        "recommended_steps": "step 1 as string instead of list",
        "risks": ["Risk 1"],
        "success_metrics": ["Metric 1"],
        "limitations": "None",
    }

    mock_chat_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": json.dumps(invalid_payload)}}]}
    )

    with patch("app.services.action_narrative_generator.chat_completion", mock_chat_completion):
        with pytest.raises(ValueError) as exc_info:
            await generator.enrich_candidates([candidate])

    assert "must be a list" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_enrich_batch_multiple_candidates():
    generator = ActionNarrativeGenerator()
    candidates = [
        _make_candidate(action_type=f"INV-00{i}", rule_label=f"label_{i}")
        for i in range(1, 4)
    ]

    async def _mock_call(messages, **kwargs):
        user_content = messages[1]["content"]
        # Echo back action_type in title
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "title": f"Recommendation for {json.loads(user_content.split('business recommendation:\n')[1].split('\n\n')[0])['action_type']}",
                            "rationale": "Custom rationale",
                            "recommended_steps": ["Step A", "Step B"],
                            "risks": ["Risk A"],
                            "success_metrics": ["Metric A"],
                            "limitations": "Limitation A",
                        })
                    }
                }
            ]
        }

    with patch("app.services.action_narrative_generator.chat_completion", side_effect=_mock_call):
        enriched = await generator.enrich_candidates(candidates)

    assert len(enriched) == 3
    for i, c in enumerate(enriched, start=1):
        assert c.title == f"Recommendation for INV-00{i}"
        assert c.ai_generated is True
