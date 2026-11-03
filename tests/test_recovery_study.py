def test_constructed_study_spans_and_families_are_reproducible():
    from benchmark.recovery_study import cases

    first = cases(2)
    assert first == cases(2)
    assert len(first) == 50
    assert len({x[0] for x in first}) == 10
    for _, _, text, start, end in first:
        assert 0 <= start < end <= len(text)
        assert "250 บาท" in text


def test_study_publishes_no_source_values():
    import json

    from benchmark.recovery_study import measure

    value = "081\u200b-234-5678"
    case = ("synthetic", "hidden", "โทร " + value, 4, 4 + len(value))
    result = measure([case], recovery=True, mode="token")
    assert result["safe_release"] == 1
    assert result["unsafe_release"] == 0
    assert result["restore_exact"] == 1
    assert value not in json.dumps(result)
