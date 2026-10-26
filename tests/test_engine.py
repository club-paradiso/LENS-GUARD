import json
import math
import pytest
from lens_guard.engine import Observation, analyze
from lens_guard.demo import demo_report, scenario
from lens_guard.evaluation import evaluate


def test_demo_deterministic_and_honest():
    a = demo_report()
    assert a == demo_report()
    assert a['provenance'] == 'synthetic_demo'
    assert a['simulation']['physical_devices'] == 0
    assert len(a['devices']) == 5
    assert '02:00:' not in json.dumps(a)
    assert any(d['status'] == 'candidate' for d in a['devices'])


def test_pseudonyms_rotate_and_never_expose_mac():
    data = scenario('camera_stream')
    a, b = analyze(data, 'unverified_file'), analyze(data, 'unverified_file')
    assert a['devices'][0]['id'] != b['devices'][0]['id']
    assert data[0].source not in json.dumps(a)


@pytest.mark.parametrize('data', [[], [Observation(0, 'x', 1500)], scenario('iot_sensor')])
def test_insufficient_is_not_safe(data):
    report = analyze(data, 'synthetic_evaluation')
    assert not any(d['status'] == 'candidate' for d in report['devices'])
    assert 'safe' in ' '.join(report['limitations'])
    assert all(d['score'] is None for d in report['devices'])


@pytest.mark.parametrize('stamp', [math.nan, math.inf, -math.inf])
def test_invalid_timestamps(stamp):
    with pytest.raises(ValueError):
        analyze([Observation(stamp,'x',100)], 'unverified_file')


def test_bounds_and_sorting():
    data = scenario('camera_stream')
    assert analyze(data, 'synthetic', salt=b'x') == analyze(reversed(data), 'synthetic', salt=b'x')
    with pytest.raises(ValueError):
        analyze([Observation(0,'x',100),Observation(3601,'x',100)], 'synthetic')


def test_known_confounders_are_reported_not_hidden():
    result = evaluate()
    assert result['sessions'] == 96
    assert result['physical_devices'] == 0
    assert result['confusion_matrix']['fp'] > 0
    assert result['confusion_matrix']['fn'] > 0
    assert result['per_profile']['video_call']['candidates'] > 0
    assert sum(result['confusion_matrix'].values()) == 96
