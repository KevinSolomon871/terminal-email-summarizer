import os
import sys

# Silence gRPC, C++ runtime logging, and deprecation notices
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GLOG_minloglevel"] = "2"
os.environ["PYTHONWARNINGS"] = "ignore"

import warnings
warnings.filterwarnings("ignore")

import contextlib
import email
from email.header import decode_header
import imaplib
import io
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

load_dotenv()
console = Console(record=True)

# --- Account Credentials ---
COLLEGE_USER = os.getenv("COLLEGE_EMAIL_USER") or os.getenv("EMAIL_USER")
COLLEGE_PASS = os.getenv("COLLEGE_EMAIL_PASS") or os.getenv("EMAIL_PASS")
PERSONAL_USER = os.getenv("PERSONAL_EMAIL_USER")
PERSONAL_PASS = os.getenv("PERSONAL_EMAIL_PASS")
API_KEY = os.getenv("GEMINI_API_KEY")

CACHE_FILE = Path.home() / ".mail_cache.txt"

if not COLLEGE_USER or not COLLEGE_PASS or not API_KEY:
    console.print("[bold red]Error: Missing credentials or GEMINI_API_KEY in .env[/bold red]")
    sys.exit(1)

# --- Sensitive Guardrail ---
SKIP_KEYWORDS = [
    "otp", "one time password", "verification code", "security code",
    "bank statement", "transaction alert", "debit alert", "credit alert",
    "password reset", "login alert"
]

def is_sensitive(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in SKIP_KEYWORDS)

# --- Fast IMAP Fetcher ---
def fetch_inbox_headers(account_tuple):
    user, pwd, label = account_tuple
    if not user or not pwd:
        return []

    t0 = time.time()
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=4)
        mail.login(user, pwd)
        mail.select("inbox", readonly=True)

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            mail.logout()
            console.print(f"[dim]• {label}: 0 unread ({time.time() - t0:.2f}s)[/dim]")
            return []

        ids = messages[0].split()[-5:]
        ids_str = b",".join(ids).decode("ascii")

        # Batch-fetch only headers to bypass heavy email payloads & attachments
        status, data = mail.fetch(ids_str, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
        mail.logout()

        if status != "OK":
            return []

        results = []
        for item in data:
            if not isinstance(item, tuple):
                continue

            raw_header = item[1]
            msg = email.message_from_bytes(raw_header)

            sub_raw, enc = decode_header(msg.get("Subject", "No Subject"))[0]
            if isinstance(sub_raw, bytes):
                subject = sub_raw.decode(enc if enc else "utf-8", errors="ignore")
            else:
                subject = str(sub_raw)

            sender = msg.get("From", "Unknown").split("<")[0].strip().strip('"')

            # Drop sensitive OTPs / alerts locally before LLM ingestion
            if is_sensitive(subject):
                continue

            results.append({
                "account": label,
                "from": sender[:30],
                "subject": subject.strip()[:85]
            })

        console.print(f"[dim]• {label}: {len(results)} fetched ({time.time() - t0:.2f}s)[/dim]")
        return results
    except Exception as e:
        console.print(f"[dim yellow]• {label} skipped: {e}[/dim yellow]")
        return []

# --- Gemini Generation (AFC Warning Suppressed) ---
def synthesize(emails):
    t0 = time.time()
    client = genai.Client(api_key=API_KEY)

    prompt = f"""
You are an executive terminal briefing assistant. Review these unread emails and return an ultra-concise daily brief.
Filter out routine promotional circulars, generic newsletters, and spam.
Flag pending deadlines, required actions, and important institutional or account notices.

EMAILS:
{emails}

Strictly output using this clean Markdown structure (do not include code fences or preamble):

### 🚨 Action Required & Deadlines
- [Account] **Action/Task** — Due date or instructions (write 'None' if no pending actions exist)

### 📢 Important Updates
- [Account] **Sender/Subject** — 1 punchy sentence summary

*Filtered Noise:* X promo circulars / spam ignored.
"""

    candidate_models = [
        "models/gemini-3.5-flash",
        "models/gemini-3.8-flash",
        "models/gemini-2.5-pro",
        "models/gemini-3.1-flash-lite",
        "models/gemini-3.1-pro-preview",
    ]

    response = None
    last_error = None

    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    break
            except Exception as e:
                last_error = e
                continue

    if not response or not getattr(response, "text", None):
        raise RuntimeError(f"All candidate Gemini models failed. Last error: {last_error}")

    console.print(f"[dim]• Gemini API: done ({time.time() - t0:.2f}s)[/dim]")
    return response.text
# --- Main Flow ---
def main():
    start_total = time.time()
    console.print("[cyan]Syncing inboxes...[/cyan]")

    accounts = [(COLLEGE_USER, COLLEGE_PASS, "College")]
    if PERSONAL_USER and PERSONAL_PASS:
        accounts.append((PERSONAL_USER, PERSONAL_PASS, "Personal"))

    # Parallel IMAP query across College and Personal accounts
    with ThreadPoolExecutor(max_workers=2) as executor:
        batch = executor.map(fetch_inbox_headers, accounts)

    emails = [e for account_list in batch for e in account_list]

    if not emails:
        clean_msg = "[bold green]✔ All inboxes clean. No unread emails.[/bold green]"
        console.print(clean_msg)
        try:
            CACHE_FILE.write_text(clean_msg, encoding="utf-8")
        except Exception:
            pass
        return

    summary_md = synthesize(emails)
    timestamp = datetime.now().strftime("%I:%M %p")

    console.print("")
    console.print(
        Panel(
            Markdown(summary_md),
            title=f"[bold white]⚡ Daily Briefing ({timestamp})[/bold white]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    elapsed_line = f"[bold dim]Total execution: {time.time() - start_total:.2f}s[/bold dim]\n"
    console.print(elapsed_line)

    # Save output to cache for instantaneous terminal startup
    try:
        CACHE_FILE.write_text(console.export_text(), encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    main()