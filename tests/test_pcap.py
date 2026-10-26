import io
import json
import struct
import pytest
from scapy.all import Ether, Raw, Dot11, RadioTap, PcapWriter, PcapNgWriter
from lens_guard.pcap import analyze_capture, normalize_allowlist, parse_capture
from lens_guard.demo import write_fixture

MAC='02:00:00:00:00:01'
AP='02:00:00:00:00:ff'


def capture(tmp_path, packets, ng=False, **options):
    path=tmp_path / ('sample.pcapng' if ng else 'sample.pcap')
    with (PcapNgWriter(str(path)) if ng else PcapWriter(str(path), **options)) as w:
        for i,p in enumerate(packets):
            p.time=1700000000 + i * .1
            w.write(p)
    return path.read_bytes()


@pytest.mark.parametrize('ng', [False,True])
def test_ethernet_and_pcapng(tmp_path,ng):
    data=capture(tmp_path,[Ether(src=MAC,dst=AP)/Raw(b'PRIVATE-CONTENT')]*120,ng)
    r=analyze_capture(data,[MAC], 'synthetic_file')
    assert r['packet_count']==120
    assert r['provenance']=='synthetic_file'
    assert r['diagnostics']['visibility']=='ethernet_source_only'
    assert 'PRIVATE-CONTENT' not in json.dumps(r)
    assert MAC not in json.dumps(r)


@pytest.mark.parametrize('nano,endian', [(False,'<'),(True,'<'),(False,'>'),(True,'>')])
def test_timestamp_resolution(tmp_path,nano,endian):
    data=capture(tmp_path,[Ether(src=MAC)/Raw(bytes(90))]*2,nano=nano,endianness=endian)
    obs,_=parse_capture(data,[MAC])
    assert obs[1].timestamp-obs[0].timestamp==pytest.approx(.1,abs=1e-6)


def test_synthetic_fixture_end_to_end(tmp_path):
    p=tmp_path/'demo.pcap'
    write_fixture(p)
    r=analyze_capture(p.read_bytes(),[MAC],'synthetic_file')
    assert r['devices'][0]['status']=='candidate'


def test_wifi_direction_encryption_retry_rssi(tmp_path):
    def wifi(flags,subtype=0):
        return RadioTap(present='dBm_AntSignal',dBm_AntSignal=-48)/Dot11(type=2,subtype=subtype,FCfield=flags,addr1=AP,addr2=MAC,addr3=AP)/Raw(bytes(1200))
    data=capture(tmp_path,[wifi(0x41),wifi(2),wifi(9),wifi(1,4),wifi(3)])
    obs,d=parse_capture(data,[MAC])
    assert len(obs)==1
    assert obs[0].source==MAC and obs[0].rssi==-48
    assert d['retry_frames']==1 and d['not_station_uplink']==3


def test_bare_80211(tmp_path):
    p=Dot11(type=2,FCfield=1,addr1=AP,addr2=MAC,addr3=AP)/Raw(bytes(90))
    obs,_=parse_capture(capture(tmp_path,[p]),[MAC])
    assert len(obs)==1


def test_allowlist_filters(tmp_path):
    data=capture(tmp_path,[Ether(src=MAC)/Raw(bytes(100))])
    r=analyze_capture(data,[AP])
    assert r['packet_count']==0 and r['devices']==[]
    assert r['diagnostics']['outside_allowlist']==1


@pytest.mark.parametrize('value', [[],['bad'],['../../secret'],['01:02:03:04:05'],['00:00:00:00:00:gg']])
def test_invalid_allowlist(value):
    with pytest.raises(ValueError):normalize_allowlist(value)


@pytest.mark.parametrize('ng', [False, True])
def test_truncated_files_rejected(tmp_path,ng):
    data=capture(tmp_path,[Ether(src=MAC)/Raw(bytes(1200))],ng)
    with pytest.raises(ValueError):analyze_capture(data[:-7],[MAC])


@pytest.mark.parametrize('data', [b'', b'not a pcap'*12, bytes(50)])
def test_invalid_files(data):
    with pytest.raises(ValueError):analyze_capture(data,[MAC])


def test_unsupported_linktype():
    data=struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,101)
    with pytest.raises(ValueError,match='Unsupported'):analyze_capture(data,[MAC])


def test_capture_size_limit():
    with pytest.raises(ValueError,match='32 MiB'):analyze_capture(bytes(32*1024*1024+1),[MAC])
