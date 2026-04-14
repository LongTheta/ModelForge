from app.inference import MODEL_VERSION, get_classifier, reset_classifier_for_tests


def test_ticket_model_train_and_predict() -> None:
    reset_classifier_for_tests()
    m = get_classifier()
    m.ensure_loaded()
    assert m.is_ready
    label, conf, scores = m.predict("need vpn access for contractor")
    assert label == "access_request"
    assert 0.0 <= conf <= 1.0
    assert abs(sum(scores.values()) - 1.0) < 1e-5
    assert MODEL_VERSION
