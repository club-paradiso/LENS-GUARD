from fastapi.testclient import TestClient
from lens_guard.api import app
from lens_guard.demo import write_fixture

client=TestClient(app)
HEADERS={'x-lens-guard':'local-analysis','x-authorized':'yes','x-device-allowlist':'02:00:00:00:00:01','x-source-kind':'synthetic_file'}


def test_health_no_capture():
    r=client.get('/api/health')
    assert r.status_code==200
    assert r.json()['capture_running'] is False
    assert r.headers['cache-control']=='no-store'


def test_demo_endpoint():
    assert client.get('/api/demo').json()['provenance']=='synthetic_demo'
    assert client.get('/api/demo?seconds=999999').status_code==422


def test_authorization_and_cross_origin():
    assert client.post('/api/analyze',content=b'x').status_code==403
    assert client.post('/api/analyze',headers={'x-lens-guard':'local-analysis'},content=b'x').status_code==400
    assert client.post('/api/analyze',headers={**HEADERS,'origin':'https://evil.example'},content=b'x').status_code==403
    assert client.get('/api/health',headers={'host':'evil.example'}).status_code==403


def test_upload_and_errors(tmp_path):
    p=tmp_path/'synthetic.pcap';write_fixture(p)
    r=client.post('/api/analyze',headers=HEADERS,content=p.read_bytes())
    assert r.status_code==200
    assert r.json()['provenance']=='synthetic_file'
    assert r.json()['devices'][0]['status']=='candidate'
    assert r.json()['devices'][0]['comparison']['rules-0.1']['status']=='candidate'
    assert r.json()['provenance_notice']
    assert client.post('/api/analyze',headers=HEADERS,content=b'bad').status_code==422
    assert client.post('/api/analyze',headers={**HEADERS,'x-source-kind':'verified_real'},content=p.read_bytes()).status_code==422


def test_evaluation_summary_is_labeled_synthetic():
    r=client.get('/api/evaluation').json()
    assert r['provenance']=='synthetic_evaluation' and 'not real-world' in r['disclaimer']
    assert set(r['splits'])=={'dev','test','shift'} and 'rows' not in r
    assert r['splits']['test']['rules-0.1']['confusion_matrix']
