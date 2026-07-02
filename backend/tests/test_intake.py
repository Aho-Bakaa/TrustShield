"""Channel classification tests."""
from app.intake import build_request, classify_channel
from app.schemas import ChannelType


def test_classify_social_by_host():
    assert classify_channel("check this https://t.me/xyz tips", False, None) == ChannelType.SOCIAL
    assert classify_channel("https://twitter.com/user/status/1", False, None) == ChannelType.SOCIAL


def test_classify_bare_url():
    assert classify_channel("http://sebi-kyc-verify.xyz/login", False, None) == ChannelType.URL


def test_classify_email_long_text():
    text = "Subject: hello\nDear investor, " + "x" * 120
    assert classify_channel(text, False, None) == ChannelType.EMAIL


def test_audio_channel_when_audio_present():
    assert classify_channel("", True, None) == ChannelType.AUDIO


def test_hint_overrides():
    assert classify_channel("some text", False, ChannelType.SOCIAL) == ChannelType.SOCIAL


def test_build_request_extracts_links_and_entities():
    req = build_request(text="SEBI alert: verify at http://sebi-kyc-verify.xyz/login now")
    assert req.channel_type in (ChannelType.EMAIL, ChannelType.URL)
    assert len(req.links) == 1
    assert any(e.text == "SEBI" for e in req.entities)
