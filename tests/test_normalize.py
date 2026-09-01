from src.analysis.normalize import classify_result


def test_classification_distinguishes_order_and_business_semantics() -> None:
    assert classify_result("03_seq_collision_a", False, False) == "AMBIGUOUS_ORDER"
    assert classify_result("08_history_a", True, False) == "BUSINESS_SEMANTICS"
    assert classify_result("08_history_b", True, True) == "CONFIGURATION_DEPENDENT"
    assert classify_result("01_duplicate", True, True) == "HANDLED"
