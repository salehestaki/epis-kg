"""Tests that don't require network / LLM / datasets."""

from epistemic_math import EpistemicParams
from evaluation.liar import LABEL_TO_SCORE, _label_to_name
from evaluation.pipeline import ClaimBlueprint, ScoredSample, score_with_params


def test_label_scale_is_monotonic():
    order = ["pants-fire", "false", "barely-true", "half-true", "mostly-true", "true"]
    scores = [LABEL_TO_SCORE[o] for o in order]
    assert scores == sorted(scores)
    assert scores[0] == 0.0 and scores[-1] == 1.0


def test_int_label_mapping():
    # HF int order: false, half-true, mostly-true, true, barely-true, pants-fire
    assert _label_to_name(0) == "false"
    assert _label_to_name(3) == "true"
    assert _label_to_name(5) == "pants-fire"
    assert _label_to_name("mostly-true") == "mostly-true"
    assert _label_to_name(99) is None


def _sample(truth: float, active_rhetoric: int, n_support: int) -> ScoredSample:
    return ScoredSample(
        truth_score=truth,
        claims=[
            ClaimBlueprint(
                a_priori_credibility=0.5,
                n_support=n_support,
                contradictions_in_degree=0,
                total_degree=1 + n_support,
                age_days=0.0,
                rhetoric=[(0.9, True) for _ in range(active_rhetoric)],
            )
        ],
    )


def test_score_with_params_rewards_evidence_penalises_rhetoric():
    params = EpistemicParams()
    samples = [
        _sample(truth=1.0, active_rhetoric=0, n_support=3),  # truthful, clean
        _sample(truth=0.0, active_rhetoric=3, n_support=0),  # false, manipulative
    ]
    preds, truths = score_with_params(samples, params)
    assert truths == [1.0, 0.0]
    # The clean, well-supported claim should score far higher than the
    # rhetoric-laden one — i.e. EIS tracks veracity in the right direction.
    assert preds[0] > preds[1]


def test_score_with_params_respects_hyperparameters():
    lenient = EpistemicParams(alpha=0.0)  # ignore rhetoric
    strict = EpistemicParams(alpha=1.5)   # punish rhetoric hard
    sample = [_sample(truth=0.0, active_rhetoric=3, n_support=0)]
    lenient_pred = score_with_params(sample, lenient)[0][0]
    strict_pred = score_with_params(sample, strict)[0][0]
    assert strict_pred < lenient_pred
