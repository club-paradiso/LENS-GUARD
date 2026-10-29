import json
from pathlib import Path
import pytest
from scapy.all import Ether, Raw, Dot11, RadioTap, PcapWriter
from lens_guard.demo import scenario, scenario_v1, write_fixture
from lens_guard.engine import RULE_FINGERPRINT, Observation, analyze, burst_residual, periodicity
from lens_guard.evaluation import SPLITS
from lens_guard.pcap import analyze_capture, parse_capture

MAC = '02:00:00:00:00:01'
AP = '02:00:00:00:00:ff'
PEER = '02:00:00:00:00:aa'
ROOT = Path(__file__).resolve().parents[1]


def capture(tmp_path, packets):
    path = tmp_path / 'direction.pcap'
    with PcapWriter(str(path)) as w:
        for i, p in enumerate(packets):
            p.time = 1700000000 + i * .1
            w.write(p)
    return path.read_bytes()


def dot11(flags, addr1, addr2, addr3, body=b'PRIVATE-CONTENT'):
    return RadioTap() / Dot11(type=2, FCfield=flags, addr1=addr1, addr2=addr2, addr3=addr3) / Raw(body)


def test_wifi_address_fields(tmp_path):
    frames = [
        dot11(0x01, AP, MAC, PEER),   # To DS: TA = SA = MAC -> tx
        dot11(0x02, MAC, AP, PEER),   # From DS: RA = DA = MAC -> rx
        dot11(0x01, AP, PEER, MAC),   # To DS, MAC only as DA in addr3 (relay) -> not counted
        dot11(0x02, PEER, AP, MAC),   # From DS, MAC only as SA in addr3 (relay) -> not counted
        dot11(0x00, MAC, PEER, AP),   # IBSS -> excluded
    ]
    obs, d = parse_capture(capture(tmp_path, frames), [MAC])
    assert [(o.source, o.direction) for o in obs] == [(MAC, 'tx'), (MAC, 'rx')]
    assert d['outside_allowlist'] == 2 and d['not_infrastructure_data'] == 1
    assert d['tx_frames'] == 1 and d['rx_frames'] == 1
    assert d['visibility'] == 'wifi_infrastructure_tx_rx'


def test_ethernet_src_dst_and_both_allowlisted(tmp_path):
    frames = [Ether(src=MAC, dst=AP) / Raw(bytes(100)), Ether(src=AP, dst=MAC) / Raw(bytes(100)),
              Ether(src=PEER, dst=AP) / Raw(bytes(100))]
    obs, d = parse_capture(capture(tmp_path, frames), [MAC])
    assert [o.direction for o in obs] == ['tx', 'rx'] and d['outside_allowlist'] == 1
    obs, _ = parse_capture(capture(tmp_path, frames[:1]), [MAC, AP])
    assert sorted((o.source, o.direction) for o in obs) == [(MAC, 'tx'), (AP, 'rx')]


def test_capture_span_sets_window_without_absolute_time(tmp_path):
    frames = [Ether(src=PEER, dst=AP) / Raw(bytes(60))] + [Ether(src=MAC, dst=AP) / Raw(bytes(60))] * 3
    r = analyze_capture(capture(tmp_path, frames), [MAC], 'synthetic_file')
    assert r['duration_s'] == pytest.approx(.3)
    assert '1700000000' not in json.dumps(r) and 'window' not in r['diagnostics']


def test_payload_and_mac_never_exposed(tmp_path):
    frames = [dot11(0x01, AP, MAC, PEER), dot11(0x02, MAC, AP, PEER),
              Ether(src=AP, dst=MAC) / Raw(b'PRIVATE-CONTENT')]
    for frame in frames:
        r = analyze_capture(capture(tmp_path, [frame] * 120), [MAC], 'synthetic_file')
        text = json.dumps(r)
        assert 'PRIVATE' not in text and MAC not in text and AP not in text and PEER not in text


def test_spike_train_period_detected():
    series = [1000.0] * 600
    for i in range(0, 600, 20):
        series[i] = 8000.0
    score, period = periodicity(burst_residual(series))
    assert period == 2.0 and score > 0.9


@pytest.mark.parametrize('series', [[1000.0, 2000.0] * 300, [1500.0] * 600, [0.0] * 600])
def test_frame_rate_aliasing_and_constant_rate_are_not_periodic(series):
    # 15 fps in 100 ms bins alternates one and two frames; that is not a key-frame period.
    assert periodicity(burst_residual(series)) == (None, None)


def test_missing_direction_abstains_instead_of_zero_fill():
    items = [Observation(p.timestamp, p.source, p.size, p.rssi) for p in scenario('camera_stream', 1)]
    device = analyze(items, 'synthetic_evaluation', window=(0, 60))['devices'][0]
    assert device['status'] == 'insufficient_direction' and device['score'] is None
    assert device['abstain_reasons'] == ['insufficient_direction']
    uplink = next(p for p in device['parts'] if p['feature'] == 'Uplink dominance')
    assert uplink['points'] is None and device['features']['uplink_ratio'] is None
    assert device['direction']['available'] is False
    assert device['comparison']['rules-0.1']['status'] == 'candidate'


def test_one_sided_capture_is_flagged():
    items = [p for p in scenario('camera_stream', 1) if p.direction == 'tx']
    device = analyze(items, 'synthetic_evaluation', window=(0, 60))['devices'][0]
    assert any('one-sided' in p['note'] for p in device['parts'])


def test_rules_01_rows_match_phase1_commit():
    frozen = json.loads((ROOT / 'tests/data/rules-0.1-phase1.json').read_text())['rows']
    for profile, seed, score, status in frozen:
        report = analyze(scenario_v1(profile, seed), 'synthetic_evaluation')
        legacy = report['devices'][0]['comparison']['rules-0.1'] if report['devices'] else {'score': None}
        assert legacy['score'] == score, (profile, seed)


def test_splits_do_not_share_seeds_and_shift_uses_other_generator():
    seeds = [set(s['seeds']) for s in SPLITS.values()]
    assert not (seeds[0] & seeds[1] or seeds[0] & seeds[2] or seeds[1] & seeds[2])
    assert SPLITS['shift']['variant'] == 'shift' and SPLITS['dev']['variant'] == SPLITS['test']['variant'] == 'base'
    assert scenario('camera_stream', 1, variant='base') != scenario('camera_stream', 1, variant='shift')


def test_preregistration_matches_current_rules():
    text = (ROOT / 'docs/PREREGISTRATION.md').read_text()
    assert RULE_FINGERPRINT in text


def test_fixture_contains_both_directions(tmp_path):
    p = tmp_path / 'fixture.pcap'
    write_fixture(p, seconds=20)
    r = analyze_capture(p.read_bytes(), [MAC], 'synthetic_file')
    assert r['devices'][0]['direction'] == {'available': True, 'tx_frames': r['diagnostics']['tx_frames'],
                                            'rx_frames': r['diagnostics']['rx_frames']}
    assert r['diagnostics']['rx_frames'] > 0
