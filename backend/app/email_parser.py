""".eml email file parser.

Extracts headers, authentication results, and body from .eml files
(standard MIME format as exported by Gmail/Outlook/Thunderbird).

Preserves the full header chain (DKIM, SPF, DMARC, Authentication-Results)
which is critical for phishing analysis — something copy-paste can't do.
"""
from __future__ import annotations

import email
import re
from email.policy import default


def parse_eml(data: bytes) -> dict:
    msg = email.message_from_bytes(data, policy=default)

    headers = {}
    for key in ("from", "to", "subject", "date", "reply-to", "message-id",
                "dkim-signature", "authentication-results", "received-spf",
                "return-path", "list-unsubscribe", "content-type"):
        val = msg.get(key, "")
        if val:
            headers[key] = str(val)[:500]

    dkim = bool(headers.get("dkim-signature"))
    spf_pass = False
    dmarc_pass = False
    auth = (headers.get("authentication-results") or "").lower()
    if "dkim=pass" in auth:
        dkim = True
    if "spf=pass" in auth:
        spf_pass = True
    if "dmarc=pass" in auth:
        dmarc_pass = True

    from_addr = headers.get("from", "")
    reply_to = headers.get("reply-to", "")
    spf_header = (headers.get("received-spf") or "").lower()
    if "pass" in spf_header:
        spf_pass = True

    body_text = ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not body_text:
                try:
                    payload = part.get_content()
                    body_text = str(payload)[:5000] if payload else ""
                except Exception:
                    pass
            elif ct == "text/html" and not body_html:
                try:
                    payload = part.get_content()
                    body_html = str(payload)[:10000] if payload else ""
                except Exception:
                    pass
    else:
        ct = msg.get_content_type()
        try:
            content = str(msg.get_content())[:5000]
        except Exception:
            content = ""
        if ct == "text/html":
            body_html = content
        else:
            body_text = content

    body = body_text or _strip_html(body_html) or ""

    urls = re.findall(r'https?://[^\s<>"\')\]]+', body + " " + body_html)

    return {
        "headers": headers,
        "from_addr": from_addr,
        "to_addr": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "body": body[:5000],
        "urls": urls[:20],
        "auth_results": {
            "dkim_pass": dkim,
            "spf_pass": spf_pass,
            "dmarc_pass": dmarc_pass,
        },
        "dkim_raw": headers.get("dkim-signature", ""),
        "auth_raw": headers.get("authentication-results", ""),
    }


def _strip_html(html: str) -> str:
    import re
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.I)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.I)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = re.sub(r'</?[a-z][a-z0-9]*(?:\s[^>]*)?>', '', text, flags=re.I)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    return text.strip()
