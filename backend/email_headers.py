import re
from email.utils import parseaddr


def email_header_flags(headers: dict[str, str]) -> list[str]:
    values = {name.lower(): value for name, value in headers.items()}
    from_value = values.get("from", "")
    reply_to = values.get("reply-to", "")
    from_address = parseaddr(from_value)[1].strip().lower()
    reply_to_address = parseaddr(reply_to)[1].strip().lower()
    flags = []
    if reply_to_address and reply_to_address != from_address:
        flags.append("Reply-To does not match From")

    received_spf = values.get("received-spf", "").lower()
    authentication = values.get("authentication-results", "").lower()
    if "fail" in received_spf or re.search(r"\bspf\s*=\s*fail\b", authentication):
        flags.append("SPF failed")
    if re.search(r"\bdkim\s*=\s*fail\b", authentication):
        flags.append("DKIM failed")
    return flags
