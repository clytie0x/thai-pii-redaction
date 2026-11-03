def test_planner_is_compared_to_distinct_experimental_policies():
    from benchmark.pdpa_workflow_study import evaluate_workflows

    result = evaluate_workflows()
    assert result["cases"] >= 16
    assert result["methods"]["basis_lifecycle"]["passed"] == result["cases"]
    assert result["methods"]["uniform_consent"]["passed"] < result["cases"]
    assert result["methods"]["manual_only"]["passed"] < result["cases"]
    assert result["execution"] == "none"
