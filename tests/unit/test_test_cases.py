import pytest

from app.modules.grading.test_cases import TestCaseSpecError as SpecError
from app.modules.grading.test_cases import parse_test_cases


def test_parse_text_json_spec():
    cases = parse_test_cases('[{"input":"2 3\\n","expected_output":"5\\n"}]')
    assert cases[0].input == "2 3\n"
    assert cases[0].expected_output == "5\n"


@pytest.mark.parametrize("raw", ["not json", "[]", "{}", '[{"input":"x"}]',
                                 '[{"input":1,"expected_output":"x"}]'])
def test_invalid_spec_stops_before_execution(raw):
    with pytest.raises(SpecError):
        parse_test_cases(raw)
