"""Tests for deterministic observable extraction."""
from extractors import extract_observables


def test_ipv4_basic():
    text = "Connection from 185.220.101.45 to internal host."
    result = extract_observables(text)
    assert result["ipv4"] == ["185.220.101.45"]


def test_ipv4_rejects_invalid_octet():
    text = "Bogus IP 999.999.999.999 in log."
    result = extract_observables(text)
    assert result["ipv4"] == []


def test_ipv4_dedupes():
    text = "Saw 10.0.0.1 then 10.0.0.1 again."
    result = extract_observables(text)
    assert result["ipv4"] == ["10.0.0.1"]


def test_email_basic():
    text = "Phish from ceo@anthrop1c.com requesting wire transfer."
    result = extract_observables(text)
    assert result["email"] == ["ceo@anthrop1c.com"]


def test_url_basic():
    text = "User clicked https://evil.com/login before reporting."
    result = extract_observables(text)
    assert result["url"] == ["https://evil.com/login"]


def test_url_strips_trailing_punctuation():
    text = "Visit https://example.com/page."
    result = extract_observables(text)
    assert result["url"] == ["https://example.com/page"]


def test_domain_excludes_email_and_url_domains():
    text = "Email from user@anthrop1c.com and click https://evil.com/x. Also seen: badguy.net."
    result = extract_observables(text)
    assert "anthrop1c.com" not in result["domain"]
    assert "evil.com" not in result["domain"]
    assert "badguy.net" in result["domain"]


def test_md5_extracted():
    text = "Hash d41d8cd98f00b204e9800998ecf8427e seen in payload."
    result = extract_observables(text)
    assert result["md5"] == ["d41d8cd98f00b204e9800998ecf8427e"]


def test_sha1_extracted():
    text = "Sha1 da39a3ee5e6b4b0d3255bfef95601890afd80709 in IOC list."
    result = extract_observables(text)
    assert result["sha1"] == ["da39a3ee5e6b4b0d3255bfef95601890afd80709"]


def test_sha256_extracted():
    text = "Sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 logged."
    result = extract_observables(text)
    assert result["sha256"] == ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"]


def test_registry_path():
    text = r"Persistence at HKLM\Software\Microsoft\Windows\CurrentVersion\Run"
    result = extract_observables(text)
    assert any("HKLM" in p for p in result["registry_path"])


def test_process_priority_over_filename():
    text = "rundll32.exe loaded comsvcs.dll"
    result = extract_observables(text)
    assert "rundll32.exe" in result["process"]
    assert "comsvcs.dll" in result["process"]
    assert "rundll32.exe" not in result["filename"]


def test_filename_doc_extension():
    text = "Ransom note README.txt appeared."
    result = extract_observables(text)
    assert "README.txt" in result["filename"]


def test_hostname_workstation_pattern():
    text = "Alert on workstation WKSTN-042 from user jsmith."
    result = extract_observables(text)
    assert "WKSTN-042" in result["hostname"]


def test_hostname_server_pattern():
    text = "Connections to srv-bastion-01 from external."
    result = extract_observables(text)
    assert "srv-bastion-01" in result["hostname"]


def test_username_after_context_word():
    text = "Employee jdoe downloaded 15GB of customer data."
    result = extract_observables(text)
    assert "jdoe" in result["username"]


def test_username_after_user_keyword():
    text = "User account is jsmith on the host."
    result = extract_observables(text)
    assert "jsmith" in result["username"]


def test_username_strips_trailing_period():
    text = "User account is jsmith. Process tree follows."
    result = extract_observables(text)
    assert "jsmith" in result["username"]
    assert "jsmith." not in result["username"]


def test_domain_excludes_process_names():
    text = "rundll32.exe loaded comsvcs.dll on the host."
    result = extract_observables(text)
    assert "rundll32.exe" not in result["domain"]
    assert "comsvcs.dll" not in result["domain"]
