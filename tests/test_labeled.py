import json
import pytest
from lens_guard.demo import write_fixture
from lens_guard.labeled import evaluate_labeled, load_manifest

MAC = '02:00:00:00:00:01'


def entry(**changes):
    base = {'file': 'call.pcap', 'devices': [{'mac': MAC, 'label': 'video_call'}], 'method': 'own_host_tcpdump',
            'authority': 'owned', 'authorization_statement': 'Synthetic test capture.',
            'captured_at': '2026-10-27T10:00:00+09:00'}
    return {**base, **changes}


def write(tmp_path, captures, **top):
    manifest = {'schema_version': 1, 'collector_statement': 'Synthetic manifest for automated tests only.',
                'captures': captures, **top}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    return path


@pytest.fixture
def captures(tmp_path):
    write_fixture(tmp_path / 'call.pcap', seconds=12, profile='camera_low_rate', seed=3)
    return tmp_path


def test_synthetic_labeled_manifest_metrics(tmp_path):
    captures = tmp_path
    for name, profile in (('camera', 'camera_stream'), ('call', 'video_call'), ('backup', 'cloud_backup')):
        write_fixture(tmp_path / f'{name}.pcap', seconds=15, profile=profile, seed=3)
    path = write(captures, [entry(file='camera.pcap', devices=[{'mac': MAC, 'label': 'camera_stream'}]),
                            entry(), entry(file='backup.pcap', devices=[{'mac': MAC, 'label': 'cloud_backup'}])])
    report = evaluate_labeled(path)
    assert report['provenance'] == 'user_declared_authorized_capture'
    assert report['authenticity'] == 'not_verified_by_program'
    assert report['labeled_devices'] == 3 and report['camera_devices'] == 1
    assert sum(report['rules-0.2']['confusion_matrix'].values()) == 3
    assert report['rules-0.2']['per_label']['camera_stream']['tp'] == 1
    assert report['rules-0.2']['per_label']['video_call']['tn'] == 1
    text = json.dumps(report)
    assert MAC not in text and '.pcap' not in text and str(captures) not in text


def test_device_missing_from_capture_is_no_observation(captures):
    report = evaluate_labeled(write(captures, [entry(devices=[{'mac': '02:00:00:00:00:09', 'label': 'idle'}])]))
    assert report['rows'][0]['rules-0.2']['status'] == 'no_observation'


@pytest.mark.parametrize('bad, message', [
    ({'file': '../outside.pcap'}, 'inside'),
    ({'file': '/etc/hosts'}, 'relative'),
    ({'file': 'missing.pcap'}, 'existing'),
    ({'file': 'manifest.json'}, 'existing'),
    ({'devices': [{'mac': 'not-a-mac', 'label': 'video_call'}]}, 'unicast'),
    ({'devices': [{'mac': '01:00:5e:00:00:01', 'label': 'video_call'}]}, 'unicast'),
    ({'devices': [{'mac': MAC, 'label': 'hidden_camera_confirmed'}]}, 'label'),
    ({'devices': [{'mac': MAC, 'label': 'video_call'}, {'mac': MAC, 'label': 'idle'}]}, 'duplicate'),
    ({'devices': [{'mac': MAC, 'label': 'video_call', 'owner': 'x'}]}, 'exactly'),
    ({'method': 'neighbor_wifi'}, 'method'),
    ({'authority': 'venue_staff_said_ok'}, 'authority'),
    ({'authorization_statement': ''}, 'authorization'),
    ({'captured_at': '2026-10-27T10:00:00'}, 'UTC offset'),
    ({'captured_at': '2999-01-01T00:00:00+00:00'}, 'future'),
    ({'payload': 'x'}, 'unknown'),
])
def test_invalid_entries_rejected(captures, bad, message):
    (captures.parent / 'outside.pcap').write_bytes((captures / 'call.pcap').read_bytes())
    with pytest.raises(ValueError, match=message):
        load_manifest(write(captures, [entry(**bad)]))


def test_invalid_manifest_shape(tmp_path, captures):
    with pytest.raises(ValueError, match='schema_version'):
        load_manifest(write(captures, [entry()], schema_version=2))
    with pytest.raises(ValueError, match='captures'):
        load_manifest(write(captures, []))
    with pytest.raises(ValueError, match='collector_statement'):
        load_manifest(write(captures, [entry()], collector_statement='ok'))
    bad = tmp_path / 'broken.json'
    bad.write_text('{')
    with pytest.raises(ValueError, match='JSON'):
        load_manifest(bad)


def test_symlink_outside_rejected(captures):
    (captures.parent / 'elsewhere.pcap').write_bytes((captures / 'call.pcap').read_bytes())
    (captures / 'link.pcap').symlink_to(captures.parent / 'elsewhere.pcap')
    with pytest.raises(ValueError, match='inside'):
        load_manifest(write(captures, [entry(file='link.pcap')]))
