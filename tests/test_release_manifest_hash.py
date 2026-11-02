import hashlib

from scripts.check_release import check_manifest_hash


def digest(content):
    return hashlib.sha256(content).hexdigest()


def test_matching_hash_leaves_bytes_unchanged(tmp_path):
    path = tmp_path / "data.jsonl"
    raw = b'{"value": 1}\n'
    path.write_bytes(raw)
    assert check_manifest_hash(path, digest(raw), True)[0]
    assert path.read_bytes() == raw


def test_crlf_is_detected_without_implicit_write(tmp_path):
    path = tmp_path / "data.jsonl"
    raw = b'{"value": 1}\r\n'
    path.write_bytes(raw)
    ok, message = check_manifest_hash(path, digest(raw.replace(b"\r\n", b"\n")))
    assert not ok and "--fix-line-endings" in message
    assert path.read_bytes() == raw


def test_explicit_repair_produces_exact_manifest_bytes(tmp_path):
    path = tmp_path / "policy.yaml"
    expected = b"version: 1\nactive: true\n"
    path.write_bytes(expected.replace(b"\n", b"\r\n"))
    assert check_manifest_hash(path, digest(expected), True)[0]
    assert path.read_bytes() == expected


def test_real_content_change_is_never_repaired(tmp_path):
    path = tmp_path / "policy.yaml"
    changed = b"version: 2\r\n"
    path.write_bytes(changed)
    ok, message = check_manifest_hash(path, digest(b"version: 1\n"), True)
    assert not ok and "nội dung khác" in message
    assert path.read_bytes() == changed


def test_missing_file_is_reported(tmp_path):
    path = tmp_path / "missing.yaml"
    assert check_manifest_hash(path, digest(b""), True) == (False, "thiếu file")
    assert not path.exists()
