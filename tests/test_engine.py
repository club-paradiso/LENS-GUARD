import json
import math
import pytest
from lens_guard.engine import Observation, analyze
from lens_guard.demo import demo_report, scenario, scenario_v1
from lens_guard.evaluation import evaluate, evaluate_v1


def test_demo_deterministic_and_honest():
    a = demo_report()
    assert a == demo_report()
    assert a['provenance'] == 'synthetic_demo'
    assert a['simulation']['physical_devices'] == 0
    assert len(a['devices']) == 6
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
    result = evaluate(splits=('dev',))
    dev = result['splits']['dev']
    assert dev['sessions'] == 180 and result['physical_devices'] == 0
    assert 'not real-world' in result['disclaimer'] and 'not real-world' in result['interpretation']
    assert dev['rules-0.2']['per_profile']['live_stream_upload']['fp'] > 0
    assert dev['rules-0.1']['per_profile']['video_call']['fp'] > 0
    assert 'test' not in result['splits'] and 'shift' not in result['splits']


def test_phase1_rules_reproduced_exactly():
    assert evaluate_v1()['metrics']['confusion_matrix'] == {'tp': 24, 'fp': 24, 'tn': 36, 'fn': 12}
    device = analyze(scenario_v1('camera_stream', 100), 'synthetic_evaluation')['devices'][0]
    assert device['comparison']['rules-0.1']['score'] == 98.7
