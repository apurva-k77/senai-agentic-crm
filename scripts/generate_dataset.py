"""Generate email-data-advanced.json (60 emails, 30+ threads) for SenAI assessment."""
import json
from datetime import datetime, timedelta
from pathlib import Path

BASE = datetime(2025, 3, 1, 9, 0, 0)
emails = []
msg_id = 1


def add(thread_id, sender, subject, body, days_offset=0, hours=0, name=None, company=None):
    global msg_id
    ts = BASE + timedelta(days=days_offset, hours=hours)
    emails.append({
        "message_id": f"msg_{msg_id:03d}",
        "thread_id": thread_id,
        "sender": sender,
        "sender_name": name or sender.split("@")[0].replace(".", " ").title(),
        "company": company,
        "subject": subject,
        "body": body,
        "timestamp": ts.isoformat() + "Z",
    })
    msg_id += 1


# thread_alice_pricing — 5 emails, 13 days
add("thread_alice_pricing", "alice.smith@greenlight-npo.org", "Nonprofit pricing inquiry",
    "Hi, we're Greenlight NPO with 45 seats. What nonprofit discount do you offer on Pro tier?", 0, name="Alice Smith", company="Greenlight NPO")
add("thread_alice_pricing", "alice.smith@greenlight-npo.org", "Re: Nonprofit pricing inquiry",
    "Thanks! Can we get 25% off annual Pro? Budget is tight.", 3)
add("thread_alice_pricing", "sales@mycompany.com", "Re: Nonprofit pricing inquiry",
    "We can offer 20% nonprofit discount on annual Pro — $38/seat/mo.", 4, name="Sales Team")
add("thread_alice_pricing", "alice.smith@greenlight-npo.org", "Ready to close — 50 seats",
    "We'll take 50 seats Pro annual at the discounted rate. Send order form?", 10)
add("thread_alice_pricing", "alice.smith@greenlight-npo.org", "Pro-rata billing after mid-cycle upgrade",
    "We upgraded 10 seats mid-cycle. How is pro-rata billing calculated on our NPO Pro annual plan?", 13,
    name="Alice Smith", company="Greenlight NPO")

# thread_bob_outage — P0 → SLA → RCA → legal
add("thread_bob_outage", "bob.t@enterprise.io", "P0: Complete API outage — production down",
    "URGENT P0: All API endpoints returning 503 since 06:00 UTC. Production is down.", 1, 6, name="Bob Turner", company="Enterprise.io")
add("thread_bob_outage", "bob.t@enterprise.io", "SLA breach — 4 hours downtime",
    "This is now a formal SLA breach. Our contract guarantees 99.9% uptime. Legal will be involved if not resolved.", 1, 10)
add("thread_bob_outage", "bob.t@enterprise.io", "RCA request",
    "We need root cause analysis within 24h per our enterprise agreement.", 2)
add("thread_bob_outage", "legal@enterprise.io", "Cease and desist — damages",
    "Our counsel demands written acknowledgment of SLA breach and damages discussion.", 3, name="Legal Team", company="Enterprise.io")

# thread_karen_refund — escalating, no replies
add("thread_karen_refund", "karen.w@retail-co.com", "Refund request — order #8821",
    "I need a refund for order #8821. Product didn't work as advertised.", 5, name="Karen Williams", company="Retail Co")
add("thread_karen_refund", "karen.w@retail-co.com", "Second request — still waiting",
    "It's been a week with NO reply. This is unacceptable.", 7)
add("thread_karen_refund", "karen.w@retail-co.com", "Churning unless resolved",
    "I'm canceling our $48k contract unless someone responds TODAY.", 9)
add("thread_karen_refund", "karen.w@retail-co.com", "Public review threat",
    "I will post detailed 1-star reviews on G2 and Trustpilot about your terrible support.", 11,
    name="Karen Williams", company="Retail Co")

# thread_eleanor_compliance — HIPAA enterprise
add("thread_eleanor_compliance", "eleanor.m@healthsys.org", "HIPAA BAA — 200 seats",
    "We need HIPAA-compliant deployment with signed BAA for 200 seats. Decision deadline March 15.", 2,
    name="Eleanor Martinez", company="HealthSys")
add("thread_eleanor_compliance", "eleanor.m@healthsys.org", "Security questionnaire",
    "Attached SOC2 and penetration test requirements. Need answers by EOD Friday.", 4)

# thread_bigcorp_rfp
add("thread_bigcorp_rfp", "procurement@bigcorp.com", "RFP — CRM platform $2.4M",
    "Formal RFP for enterprise CRM — $2.4M opportunity. Compliance audit required.", 0, name="Procurement", company="BigCorp")
add("thread_bigcorp_rfp", "compliance@bigcorp.com", "Compliance audit documentation",
    "Please provide ISO27001, GDPR DPA, and subprocessors list for audit.", 1)
add("thread_bigcorp_rfp", "admin@bigcorp.com", "New user registration — 500 seats",
    "Register 500 users under master agreement. SSO SAML required.", 2)

# Security threads
add("thread_security_login", "security-alerts@mycompany.com", "Suspicious login detected",
    "ALERT: Suspicious login from IP 185.220.101.42 for account admin@client.com", 0, name="Security Alerts")
add("thread_security_ransom", "attacker@darknet.onion", "Your data is encrypted",
    "Send 2 BTC to wallet xyz or we publish all your customer data. You have 72 hours.", 1,
    name="Unknown", company="Threat Actor")

# GDPR
add("thread_gdpr_001", "marcus.del@fintech-startup.co", "GDPR Article 20 — Data Portability Request",
    "Under GDPR Article 20, I formally request export of all personal data you hold about me "
    "marcus.del@fintech-startup.co in machine-readable format within statutory timeframe.", 6,
    name="Marcus Delgado", company="FinTech Startup")

# Spam threads
add("thread_spam_seo", "seo-guru@spam-marketing.biz", "Boost your SEO 1000%",
    "We guarantee #1 Google ranking. Buy backlinks now!!!", 0)
add("thread_spam_prince", "prince.nigeria@royal-mail.fake", "Urgent business proposal",
    "Dear friend, I am Nigerian prince with $10M needing your bank account.", 0)
add("thread_spam_cold", "cold@saas-pitch.io", "Partnership opportunity",
    "I'd love 15 minutes to discuss synergies between our AI platforms.", 1)

# thread_nadia_bug
add("thread_nadia_bug", "nadia.k@datafirm.com", "CRITICAL: Data corruption — export empty",
    "Export shows SUCCESS but downloaded CSV is empty. Mission-critical analytics broken.", 3,
    name="Nadia Kim", company="DataFirm")

# thread_chatbot_misinformation
add("thread_chatbot_misinformation", "james.p@shop-now.com", "Wrong refund info from your chatbot",
    "Your chatbot told me I get automatic full refund within 7 days no questions asked. "
    "That's not what happened. I want what was promised.", 8, name="James Park", company="Shop Now")

# Additional threads to reach 60 emails
threads_extra = [
    ("thread_dave_feature", "dave.r@startup.io", "Feature request: Slack integration", "Please add native Slack notifications.", "Dave Reed", "Startup.io"),
    ("thread_lisa_billing", "lisa.m@agency.com", "Invoice discrepancy", "Invoice #4492 shows double charge for March.", "Lisa Moore", "Agency.com"),
    ("thread_tom_bug", "tom.h@devshop.net", "Login loop bug", "Users stuck in redirect loop after SSO.", "Tom Hart", "DevShop"),
    ("thread_sara_positive", "sara.l@happyclient.com", "Love the new dashboard!", "Amazing update. Team loves analytics.", "Sara Lee", "Happy Client"),
    ("thread_mike_inquiry", "mike.b@consulting.com", "Enterprise pricing", "Quote for 300 seats Enterprise tier?", "Mike Brown", "Consulting"),
    ("thread_internal_001", "hr@internal.com", "All-hands reminder", "Reminder: Q1 all-hands Friday 3pm.", "HR Team", "Internal"),
    ("thread_internal_002", "dev@mycompany.com", "Deploy checklist", "Production deploy v2.4 checklist attached.", "Dev Team", "MyCompany"),
    ("thread_anna_compliance", "anna.c@bank.eu", "DPA signature needed", "Please countersign EU Data Processing Agreement.", "Anna Cruz", "Bank EU"),
    ("thread_paul_legal", "paul.s@lawfirm.com", "Subpoena response", "We received subpoena for user logs. Legal review needed.", "Paul Stone", "Law Firm"),
    ("thread_jen_mixed", "jen.t@mixed-signals.co", "Mixed feelings",
     "I love the product but hate the price and want a refund for last month.", "Jen Taylor", "Mixed Signals"),
    ("thread_oliver_other", "oliver.w@misc.org", "General question", "Do you support webhooks for Zapier?", "Oliver White", "Misc"),
    ("thread_rachel_billing", "rachel.g@saas.io", "Payment failed", "Card declined — need to update billing.", "Rachel Green", "SaaS.io"),
    ("thread_vik_complaint", "vik.p@angry.io", "Terrible onboarding", "Onboarding took 3 weeks. Very frustrated.", "Vik Patel", "Angry.io"),
    ("thread_emma_inquiry", "emma.d@edu.org", "Education discount?", "Do you offer education pricing for universities?", "Emma Davis", "Edu"),
    ("thread_chris_bug", "chris.n@tech.co", "API rate limit false positive", "Getting 429 despite being under quota.", "Chris Ng", "Tech Co"),
    ("thread_hannah_feature", "hannah.b@design.studio", "Dark mode request", "Please add dark mode to dashboard.", "Hannah Brooks", "Design Studio"),
    ("thread_leo_spam2", "winner@lottery-scam.net", "You won!", "Congratulations! Claim your prize now.", "Scam", "Lottery"),
    ("thread_nina_positive", "nina.s@loyal.com", "Renewal intent", "We want to renew early for 2 years.", "Nina Shaw", "Loyal Inc"),
    ("thread_oscar_outage2", "oscar.f@ops.io", "Degraded performance", "Latency spike in EU region last hour.", "Oscar F", "Ops.io"),
    ("thread_priya_compliance2", "priya.k@insurance.com", "SOC2 report request", "Need latest SOC2 Type II for vendor review.", "Priya Kumar", "Insurance"),
    ("thread_quinn_inquiry2", "quinn.a@retail.net", "API documentation", "Where is OpenAPI spec for v3?", "Quinn Adams", "Retail Net"),
    ("thread_rob_escalation", "rob.m@enterprise2.com", "Escalation — account manager",
     "I need executive escalation. Account at risk.", "Rob Martin", "Enterprise2"),
    ("thread_sophie_gdpr2", "sophie.l@privacy.eu", "Right to erasure", "Please delete all my data under GDPR Art. 17.", "Sophie Laurent", "Privacy EU"),
    ("thread_tyler_billing2", "tyler.j@corp.com", "PO number on invoice", "Add PO-9982 to next invoice.", "Tyler Jones", "Corp"),
    ("thread_uma_bug2", "uma.v@health.io", "HIPAA log access bug", "Audit logs missing for admin actions.", "Uma Varma", "Health.io"),
    ("thread_wade_feature2", "wade.c@gaming.gg", "Webhook retries", "Configure exponential backoff for webhooks?", "Wade Clark", "Gaming"),
    ("thread_xena_churn", "xena.p@churn-risk.com", "Considering alternatives", "Evaluating CompetitorX. Match their pricing?", "Xena Price", "Churn Risk"),
    ("thread_yuki_positive2", "yuki.t@japan.co.jp", "Excellent support", "Shout-out to support team for fast fix.", "Yuki Tanaka", "Japan Co"),
    ("thread_zack_security2", "zack.h@client.com", "Password reset abuse", "Multiple password reset attempts detected.", "Zack Hill", "Client"),
]

day = 0
for tid, sender, subj, body, name, company in threads_extra:
    add(tid, sender, subj, body, day % 14, day % 8, name=name, company=company)
    day += 1

# Fill to 60 if short
while len(emails) < 60:
    i = len(emails) + 1
    add(f"thread_fill_{i}", f"user{i}@example.com", f"Follow-up {i}", f"Additional message {i} for volume testing.", i % 10)

out = Path(__file__).resolve().parents[1] / "data" / "email-data-advanced.json"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump({"emails": emails, "meta": {"count": len(emails), "threads": len({e["thread_id"] for e in emails})}}, f, indent=2)
print(f"Wrote {len(emails)} emails to {out}")
