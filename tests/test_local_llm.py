"""No real model needed: loopback adapter and opt-in UI contract regression."""
import json
from copy import deepcopy

import pytest

from astrochart import local_llm


def sample(time_mode="known"):
    return {
        "time_mode": time_mode,
        "sections": [
            {"title": "ציר פעולה", "paragraphs": [
                {"kind": "axis", "semantic_text": "ייתכן דגש על התחלה מדורגת.",
                 "classifications": ["editorial_extension"],
                 "audit_statuses": ["unverified"], "provisional_time": False,
                 "evidence_text": "סוד: כתובת מקור אינה מיועדת למודל",
                 "source_refs": ["https://example.invalid/private"]},
                {"kind": "editorial-disclosure",
                 "semantic_text": "טקסט קבוע שלא אמור להישלח"},
            ]},
        ],
        "private_birth_date": "1983-01-02",
        "private_location": "private-location",
    }


def test_model_source_minimal_and_never_mutates_original():
    input_data = sample("unknown")
    copy = deepcopy(input_data)
    encoded = local_llm.build_n2_source(input_data)
    parsed = json.loads(encoded)
    assert input_data == copy
    assert parsed["time_mode"] == "unknown"
    assert parsed["source_is_scientifically_validated"] is False
    assert parsed["passages"][0]["text"] == "ייתכן דגש על התחלה מדורגת."
    assert "https://" not in encoded
    for forbidden in ("1983", "private-location", "סוד:", "טקסט קבוע"):
        assert forbidden not in encoded


@pytest.mark.parametrize("invalid", [
    {}, {"sections": [], "time_mode": "known"},
    {"sections": [], "time_mode": "invalid"},
    {"sections": "bad", "time_mode": "known"},
])
def test_missing_or_invalid_source_abstains(invalid):
    with pytest.raises(local_llm.LocalModelError):
        local_llm.build_n2_source(invalid)


def test_long_n2_rejects_without_silent_truncation():
    big = sample()
    big["sections"][0]["paragraphs"][0]["semantic_text"] = "א" * 24000
    with pytest.raises(local_llm.LocalModelError, match="ארוכה"):
        local_llm.build_n2_source(big)


@pytest.mark.parametrize("port", [0, 65536, -1, "8080", True])
def test_invalid_port_never_issues_request(port):
    with pytest.raises(local_llm.LocalModelError):
        local_llm._url(port, "/v1/models")


def test_endpoint_fixed_to_loopback_and_no_extra_paths():
    assert local_llm._url(8080, "/v1/models") == "http://127.0.0.1:8080/v1/models"
    with pytest.raises(local_llm.LocalModelError):
        local_llm._url(8080, "/redirect")


def test_explicit_generation_uses_model_discovery_and_supported_prose_only(monkeypatch):
    captured = []
    def fake_request(port, endpoint, payload=None, **kwargs):
        captured.append((port, endpoint, payload))
        if endpoint == "/v1/models":
            return {"data": [{"id": "loaded-dicta-1.7"}]}
        return {"choices": [{"finish_reason": "stop",
                             "message": {"content": "  ייתכן דגש על התחלה הדרגתית.  "}}]}
    monkeypatch.setattr(local_llm, "_request_json", fake_request)
    result = local_llm.generate_local_n2(sample("estimated"), port=9999)
    assert result == "ייתכן דגש על התחלה הדרגתית."
    assert len(captured) == 2
    assert captured[0][:2] == (9999, "/v1/models")
    port, endpoint, body = captured[1]
    assert (port, endpoint) == (9999, "/v1/chat/completions")
    assert body["model"] == "loaded-dicta-1.7"
    assert body["stream"] is False
    assert "1983" not in body["messages"][1]["content"]
    assert "הסתייגות" in body["messages"][0]["content"]


@pytest.mark.parametrize("chat_reply", [
    {"choices": []},
    {"choices": [{"message": {"content": ""}}]},
    {"choices": [{"finish_reason": "length", "message": {"content": "קטוע"}}]},
    {"choices": [{"message": {"content": ["not text"]}}]},
])
def test_invalid_model_reply_falls_back_via_exception(monkeypatch, chat_reply):
    def fake_request(port, endpoint, payload=None, **kwargs):
        if endpoint == "/v1/models":
            return {"data": [{"id": "dicta"}]}
        return chat_reply
    monkeypatch.setattr(local_llm, "_request_json", fake_request)
    with pytest.raises(local_llm.LocalModelError):
        local_llm.generate_local_n2(sample())


def test_transport_has_no_proxy_and_disallows_http_redirects(monkeypatch):
    recorded = {}
    class FakeReply:
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            pass
        def geturl(self):
            return "http://127.0.0.1:8080/v1/models"
        def read(self, max_length):
            assert max_length == local_llm.MAX_RESPONSE_BYTES + 1
            return b'{"data":[{"id":"dicta"}]}'
    class FakeOpener:
        def open(self, request, timeout):
            recorded["url"] = request.full_url
            recorded["timeout"] = timeout
            return FakeReply()
    def fake_build_opener(*handlers):
        recorded["handlers"] = handlers
        return FakeOpener()
    monkeypatch.setattr(local_llm, "build_opener", fake_build_opener)
    result = local_llm._request_json(8080, "/v1/models")
    assert result["data"][0]["id"] == "dicta"
    assert recorded["url"] == "http://127.0.0.1:8080/v1/models"
    assert any(isinstance(h, local_llm.ProxyHandler) and not h.proxies
               for h in recorded["handlers"])
    assert any(isinstance(h, local_llm._NoRedirect) for h in recorded["handlers"])


def test_redirect_like_reply_is_rejected(monkeypatch):
    class FakeReply:
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            pass
        def geturl(self):
            return "https://external.invalid/snoop"
    class FakeOpener:
        def open(self, request, timeout):
            return FakeReply()
    monkeypatch.setattr(local_llm, "build_opener", lambda *args: FakeOpener())
    with pytest.raises(local_llm.LocalModelError, match="הפנה"):
        local_llm._request_json(8080, "/v1/models")


def test_unavailable_server_fails_closed(monkeypatch):
    from urllib.error import URLError
    class Unavailable:
        def open(self, request, timeout):
            raise URLError("offline")
    monkeypatch.setattr(local_llm, "build_opener", lambda *args: Unavailable())
    with pytest.raises(local_llm.LocalModelError, match="לא ניתן לקבל תשובה"):
        local_llm.generate_local_n2(sample())


def test_dialog_has_no_implicit_ai_request_and_keeps_original_n2(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    import astrochart.interpretation_dialog as dialog_module
    from astrochart.domain import BodyPosition, Chart

    def unexpected(*args, **kwargs):
        raise AssertionError("AI request without user activation")
    monkeypatch.setattr(dialog_module, "generate_local_n2", unexpected)
    app = QApplication.instance() or QApplication([])
    chart = Chart([BodyPosition("שמש", 12.0, False)], [], None, None, False, [])
    dialog = dialog_module.RuleInterpretationDialog(chart)
    assert dialog.n2_view.toPlainText() == dialog.narrative_n2_readable
    assert dialog.local_copy_button.isEnabled() is False
    assert "לא נוצר חיבור" in dialog.local_status.text()
    dialog.close()
    app.processEvents()


def test_user_declines_then_no_ai_request(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QMessageBox
    import astrochart.interpretation_dialog as dialog_module
    from astrochart.domain import BodyPosition, Chart

    monkeypatch.setattr(dialog_module.QMessageBox, "question",
                        lambda *args: QMessageBox.StandardButton.No)
    monkeypatch.setattr(dialog_module, "generate_local_n2",
                        lambda *args, **kwargs: pytest.fail("unexpected model call"))
    app = QApplication.instance() or QApplication([])
    chart = Chart([BodyPosition("שמש", 12.0, False)], [], None, None, False, [])
    dialog = dialog_module.RuleInterpretationDialog(chart)
    dialog._start_local_generation()
    assert dialog._local_worker is None
    assert dialog.n2_view.toPlainText() == dialog.narrative_n2_readable
    dialog.close()
    app.processEvents()


def test_explicit_gui_generation_is_asynchronous_and_does_not_replace_n2(monkeypatch):
    pytest.importorskip("PySide6")
    import time
    from PySide6.QtWidgets import QApplication, QMessageBox
    import astrochart.interpretation_dialog as dialog_module
    from astrochart.domain import BodyPosition, Chart

    monkeypatch.setattr(dialog_module.QMessageBox, "question",
                        lambda *args: QMessageBox.StandardButton.Yes)
    calls = []
    def generated(report, port):
        calls.append((report["time_mode"], port))
        return "ניסוח בדיקה מקומי."
    monkeypatch.setattr(dialog_module, "generate_local_n2", generated)
    app = QApplication.instance() or QApplication([])
    chart = Chart([BodyPosition("שמש", 12.0, False)], [], None, None, False, [])
    dialog = dialog_module.RuleInterpretationDialog(chart)
    original_n2 = dialog.n2_view.toPlainText()
    dialog.local_port.setValue(8088)
    dialog._start_local_generation()
    end = time.monotonic() + 4
    while dialog._local_worker is not None and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    assert dialog._local_worker is None
    assert calls == [("known", 8088)]
    assert "ניסוח בדיקה מקומי." in dialog.local_view.toPlainText()
    assert "לא אומת אוטומטית" in dialog.local_view.toPlainText()
    assert dialog.n2_view.toPlainText() == original_n2
    assert dialog.local_copy_button.isEnabled()
    dialog.close()
    app.processEvents()


def test_failed_gui_generation_displays_unchanged_n2(monkeypatch):
    pytest.importorskip("PySide6")
    import time
    from PySide6.QtWidgets import QApplication, QMessageBox
    import astrochart.interpretation_dialog as dialog_module
    from astrochart.domain import BodyPosition, Chart

    monkeypatch.setattr(dialog_module.QMessageBox, "question",
                        lambda *args: QMessageBox.StandardButton.Yes)
    def generated(report, port):
        raise local_llm.LocalModelError("שרת לא זמין")
    monkeypatch.setattr(dialog_module, "generate_local_n2", generated)
    app = QApplication.instance() or QApplication([])
    chart = Chart([BodyPosition("שמש", 12.0, False)], [], None, None, False, [])
    dialog = dialog_module.RuleInterpretationDialog(chart)
    original_n2 = dialog.n2_view.toPlainText()
    dialog._start_local_generation()
    end = time.monotonic() + 4
    while dialog._local_worker is not None and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    assert dialog._local_worker is None
    assert "שרת לא זמין" in dialog.local_status.text()
    assert original_n2 in dialog.local_view.toPlainText()
    assert dialog.n2_view.toPlainText() == original_n2
    assert not dialog.local_copy_button.isEnabled()
    dialog.close()
    app.processEvents()
