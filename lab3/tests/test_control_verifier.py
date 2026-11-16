"""The acceptance checker must understand equivalent factual formulations."""

import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "verify_portal", Path(__file__).resolve().parents[1] / "scripts/verify_portal.py"
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def test_platform_inflection_and_acceptance_exclusion():
    answer = "iOS не поддерживается на приёмке пилота, Firefox — да, в двух последних стабильных версиях. [1][3]"
    assert verifier.facts("K07", answer) == []


def test_citation_number_is_not_a_platform_version_count():
    answer = "iOS вне приёмки пилота; Firefox поддерживается в стабильных версиях [2]"
    assert r"дв(?:е|а|ух)|2" in verifier.facts("K07", answer)


def test_download_delta_does_not_replace_total():
    assert "4320" in verifier.facts("K06", "Дополнительный трафик стоит 2160 ₽ [1]")


def test_sample_cannot_be_replaced_with_percentages():
    missing = verifier.facts(
        "K04",
        "Активация 71,7% выше 70%; удержание 45,3% ниже 50%; SEV-1 отсутствует [1]",
    )
    assert all(value in missing for value in ("86", "120", "39"))
