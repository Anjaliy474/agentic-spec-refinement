from reqhq.eval.metrics import completeness_penalty, prf1


def test_prf1():
    p, r, f = prf1(8, 2, 2)
    assert (p, r) == (0.8, 0.8)
    assert abs(f - 0.8) < 1e-9


def test_prf1_empty():
    assert prf1(0, 0, 0) == (0.0, 0.0, 0.0)


def test_completeness_penalty():
    assert completeness_penalty({"security", "performance"}, {"security"}) == 0.5
    assert completeness_penalty(set(), set()) == 0.0
