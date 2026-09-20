"""The requests CloudWhatsApp sends to the Graph API, captured with a mock transport (no network)."""
import json

import httpx
from pywa import WhatsApp

from app.channels.whatsapp import CloudWhatsApp, Row


def test_outbound_requests(tmp_path):
    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/media"):
            sent.append(("upload", req.headers.get("content-type", "")[:19]))
            return httpx.Response(200, json={"id": "MEDIA1"})
        body = json.loads(req.content)
        sent.append(("message", body))
        return httpx.Response(200, json={"messaging_product": "whatsapp",
                                         "contacts": [{"input": body["to"], "wa_id": body["to"]}],
                                         "messages": [{"id": f"wamid.{len(sent)}"}]})

    wa = WhatsApp(phone_id="123", token="t", session=httpx.Client(transport=httpx.MockTransport(handler)))
    cw = CloudWhatsApp(wa)
    png, ogg = tmp_path / "c.png", tmp_path / "v.ogg"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    ogg.write_bytes(b"OggS" + b"0" * 64)

    assert cw.buttons("+919812345678", "Menu", [("outlook", "4-week outlook"), ("change_crop", "Change crop"),
                                                ("officer", "A very long officer button title")],
                      footer="Send STOP", tracker="d1").startswith("wamid.")
    cw.list("+919812345678", "Choose", "Crops", [Row(f"crop:{i}", f"Crop {i}") for i in range(10)])
    cw.location_request("+919812345678", "Share location")
    cw.image("+919812345678", png, caption="Wait to sow", tracker="d1")
    cw.voice("+919812345678", ogg, tracker="d1")
    cw.contact("+919812345678", "ADA Kundgol", "+910000000001")

    msgs = [b for k, b in sent if k == "message"]
    btn, lst, loc, img, voice, contact = msgs
    assert btn["to"] == "919812345678" and btn["interactive"]["type"] == "button"
    titles = [b["reply"]["title"] for b in btn["interactive"]["action"]["buttons"]]
    assert len(titles) == 3 and all(len(t) <= 20 for t in titles)
    assert btn["biz_opaque_callback_data"] == "d1"
    assert lst["interactive"]["type"] == "list" and len(lst["interactive"]["action"]["sections"][0]["rows"]) == 10
    assert loc["interactive"]["type"] == "location_request_message"
    assert img["type"] == "image" and img["image"]["id"] == "MEDIA1"
    assert voice["type"] == "audio" and voice["audio"]["id"] == "MEDIA1" and voice["audio"].get("voice") is True
    assert contact["type"] == "contacts" and contact["contacts"][0]["phones"][0]["phone"] == "+910000000001"
    assert sum(1 for k, _ in sent if k == "upload") == 2


def test_buttons_with_picture_header_upload_once(tmp_path):
    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/media"):
            sent.append(("upload", None))
            return httpx.Response(200, json={"id": "777"})
        body = json.loads(req.content)
        sent.append(("message", body))
        return httpx.Response(200, json={"messaging_product": "whatsapp", "contacts": [{"input": "1", "wa_id": "1"}],
                                         "messages": [{"id": f"wamid.{len(sent)}"}]})

    wa = WhatsApp(phone_id="123", token="t", session=httpx.Client(transport=httpx.MockTransport(handler)))
    cw = CloudWhatsApp(wa)
    png = tmp_path / "b.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    for _ in range(2):
        cw.buttons("+919812345678", "Your block is Kundgol", [("blk:yes", "Yes, correct"), ("blk:no", "No, change it")],
                   image=png)
    msgs = [b for k, b in sent if k == "message"]
    assert sum(1 for k, _ in sent if k == "upload") == 1          # uploaded once, reused after
    i = msgs[0]["interactive"]
    assert i["type"] == "button" and i["header"]["type"] == "image" and i["header"]["image"]["id"] == "777"
    assert i["body"]["text"] == "Your block is Kundgol"
    assert [b["reply"]["title"] for b in i["action"]["buttons"]] == ["✅ Yes, correct", "✏️ No, change it"]
