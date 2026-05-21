"""Layer 1 — sub-10ms heuristic pre-filter."""
import re
import time
from dataclasses import dataclass

SPAM_KEYWORDS = {"seo", "backlinks", "nigerian prince", "lottery", "claim your prize", "guarantee #1"}
SPAM_DOMAINS = {".biz", ".fake", "spam-marketing", "lottery-scam", "royal-mail.fake", "darknet.onion"}
URGENT_KEYWORDS = {"urgent", "p0", "legal", "cease and desist", "ransomware", "btc", "sla breach", "critical", "encrypted"}
SECURITY_KEYWORDS = {"suspicious login", "ransomware", "send 2 btc", "password reset attempts", "data breach", "encrypted"}
INTERNAL_DOMAINS = ("@internal.com", "@mycompany.com")


@dataclass
class HeuristicResult:
    is_spam: bool = False
    is_internal: bool = False
    is_security: bool = False
    urgency_boost: int = 0
    priority_score: int = 0
    route_queue: str = "default"
    flags: list[str] = None

    def __post_init__(self):
        if self.flags is None:
            self.flags = []


def run_heuristics(sender: str, subject: str, body: str) -> HeuristicResult:
    t0 = time.perf_counter()
    text = f"{subject} {body}".lower()
    sender_l = sender.lower()
    r = HeuristicResult()

    if any(k in text for k in SECURITY_KEYWORDS) or "security-alert" in sender_l:
        r.is_security = True
        r.route_queue = "security"
        r.urgency_boost = 100
        r.priority_score = 100
        r.flags.append("security")
        return r

    if any(d in sender_l for d in SPAM_DOMAINS) or any(k in text for k in SPAM_KEYWORDS):
        r.is_spam = True
        r.route_queue = "spam"
        r.priority_score = 0
        r.flags.append("spam_heuristic")
        assert (time.perf_counter() - t0) < 0.05
        return r

    if sender_l.endswith(INTERNAL_DOMAINS):
        r.is_internal = True
        r.route_queue = "internal"
        r.flags.append("internal")
        return r

    boost = sum(10 for k in URGENT_KEYWORDS if k in text)
    r.urgency_boost = boost
    r.priority_score = min(90, 20 + boost)
    if "gdpr" in text or "article 20" in text or "article 17" in text:
        r.route_queue = "legal"
        r.priority_score = 85
        r.flags.append("compliance")
    assert (time.perf_counter() - t0) < 0.01
    return r


def sanitize_body(body: str | None, max_chars: int = 10000) -> tuple[str, bool]:
    if not body:
        return "", False
    cleaned = re.sub(r"&nbsp;|&#\d+;", " ", body, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "", False
    if len(cleaned) > max_chars:
        return cleaned[:max_chars] + "\n[TRUNCATED]", True
    return cleaned, False
