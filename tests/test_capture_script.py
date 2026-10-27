"""Static checks only: the capture script is never executed by tests or the app."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'scripts/capture-own-host.sh').read_text()


def test_capture_requires_explicit_flag_root_and_typed_confirmation():
    assert 'run=0' in SCRIPT and '--run) run=1' in SCRIPT
    assert 'Dry run. Nothing was captured.' in SCRIPT
    assert '[ "$(id -u)" -ne 0 ]' in SCRIPT and '[ ! -t 0 ]' in SCRIPT
    assert '[ "$answer" = "CAPTURE" ]' in SCRIPT
    assert 'sudo ' not in re.sub(r'(?m)^\s*(#|echo).*$', '', SCRIPT)


def test_capture_is_own_host_minimal_and_bounded():
    assert 'filter="ether host $mac"' in SCRIPT and '"$own" != "$mac"' in SCRIPT
    assert 'SNAPLEN=14' in SCRIPT and '-s "$SNAPLEN"' in SCRIPT
    assert 'MAX_SECONDS=600' in SCRIPT and 'MAX_PACKETS=200000' in SCRIPT and '-c "$packets"' in SCRIPT
    assert '$root/captures/' in SCRIPT and 'umask 077' in SCRIPT
    assert not any(label.startswith('camera') for label in re.search(r'LABELS="([^"]*)"', SCRIPT).group(1).split())


def test_capture_output_is_ignored_and_never_called_by_code():
    assert 'captures/' in (ROOT / '.gitignore').read_text().split()
    for path in (ROOT / 'src').rglob('*.py'):
        text = path.read_text()
        assert 'capture-own-host' not in text
        assert not re.search(r'\bsubprocess\b|os\.system|Popen|os\.exec', text), path
