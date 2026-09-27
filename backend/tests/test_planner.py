from unittest.mock import patch

from tests.conftest import make_parsed_response

from app.agents.planner import PlannerOutput, plan


def test_plan_parses_classification_and_subqueries():
    fake_output = PlannerOutput(
        classification="comparison",
        standalone_question="How do documents A and B differ on pricing?",
        sub_queries=["pricing in document A", "pricing in document B"],
    )
    with patch("app.agents.planner.client") as mock_client:
        mock_client.models.generate_content.return_value = make_parsed_response(fake_output)

        result = plan({"question": "how do they differ on pricing?", "chat_history": []})

    assert result["plan"] == "comparison"
    assert result["standalone_question"] == fake_output.standalone_question
    assert result["sub_queries"] == fake_output.sub_queries
    assert result["trace"][0]["agent"] == "planner"
    assert result["trace"][0]["status"] == "completed"


def test_plan_caps_subqueries_at_three():
    fake_output = PlannerOutput(
        classification="multi_hop",
        standalone_question="q",
        sub_queries=["a", "b", "c", "d", "e"],
    )
    with patch("app.agents.planner.client") as mock_client:
        mock_client.models.generate_content.return_value = make_parsed_response(fake_output)

        result = plan({"question": "q", "chat_history": []})

    assert len(result["sub_queries"]) == 3


def test_plan_falls_back_when_model_output_unparseable():
    with patch("app.agents.planner.client") as mock_client:
        mock_client.models.generate_content.return_value = make_parsed_response(None)

        result = plan({"question": "what about it?", "chat_history": []})

    assert result["plan"] == "multi_hop"
    assert result["standalone_question"] == "what about it?"
    assert result["sub_queries"] == ["what about it?"]


def test_plan_formats_chat_history_into_prompt():
    fake_output = PlannerOutput(
        classification="simple_lookup", standalone_question="q", sub_queries=["q"]
    )
    with patch("app.agents.planner.client") as mock_client:
        mock_client.models.generate_content.return_value = make_parsed_response(fake_output)

        plan(
            {
                "question": "what about it?",
                "chat_history": [{"role": "user", "content": "Tell me about the budget."}],
            }
        )

        _, kwargs = mock_client.models.generate_content.call_args
        assert "Tell me about the budget." in kwargs["contents"]
