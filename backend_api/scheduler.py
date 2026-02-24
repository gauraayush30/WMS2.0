"""
Background scheduler – runs a stock-alert job every 6 hours.

Checks every SKU against its replenishment reorder point.
If any SKU is at or below its reorder point, it generates a CSV and
emails it to every user who has alerts enabled.

Email is sent via Gmail SMTP (or any SMTP provider) using credentials
stored in these .env variables:

    MAIL_SERVER   = smtp.gmail.com
    MAIL_PORT     = 587
    MAIL_USERNAME = your_email@gmail.com
    MAIL_PASSWORD = your_app_password          # Gmail App Password (not account pw)
    MAIL_FROM     = your_email@gmail.com
"""

import csv
import io
import os
import smtplib
import logging
from datetime import datetime
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import get_all_users_with_alerts_enabled, update_last_alert_sent

# Load .env from project root (one level up from backend_api/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)


# ── Email helpers ─────────────────────────────────────────────────────────────

def _build_csv(at_risk: list[dict]) -> bytes:
    """Serialise the at-risk SKU list to CSV bytes."""
    fieldnames = [
        "sku_id", "sku_name", "current_stock", "projected_stock",
        "demand_during_lead_time", "reorder_point", "safety_stock",
        "lead_time_days", "target_stock_level", "order_quantity",
        "urgency", "message",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(at_risk)
    return output.getvalue().encode("utf-8")


def _build_html_table(at_risk: list[dict]) -> str:
    td = 'style="padding:8px 12px;border-bottom:1px solid #e5e7eb;"'
    rows = "".join(
        f"""
        <tr>
            <td {td}>{r['sku_id']}</td>
            <td {td}>{r['sku_name']}</td>
            <td {td}>{r['current_stock']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#dc2626;font-weight:700;">{r.get('projected_stock', '-')}</td>
            <td {td}>{round(r.get('demand_during_lead_time', 0))}</td>
            <td {td}>{r['reorder_point']}</td>
            <td {td}>{r['lead_time_days']}d</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#1976d2;font-weight:700;">{r.get('order_quantity', '-')}</td>
            <td {td}>{r.get('urgency', '-')}</td>
        </tr>"""
        for r in at_risk
    )
    return f"""
    <table style="width:100%;border-collapse:collapse;font-family:Segoe UI,sans-serif;font-size:14px;">
      <thead>
        <tr style="background:#1976d2;color:#fff;">
          <th style="padding:10px 12px;text-align:left;">SKU ID</th>
          <th style="padding:10px 12px;text-align:left;">SKU Name</th>
          <th style="padding:10px 12px;text-align:left;">Current Stock</th>
          <th style="padding:10px 12px;text-align:left;">Projected Stock</th>
          <th style="padding:10px 12px;text-align:left;">Forecast Demand</th>
          <th style="padding:10px 12px;text-align:left;">Reorder Point</th>
          <th style="padding:10px 12px;text-align:left;">Lead Time</th>
          <th style="padding:10px 12px;text-align:left;">Order Qty</th>
          <th style="padding:10px 12px;text-align:left;">Urgency</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def send_alert_email(to_email: str, name: str, at_risk: list[dict]) -> None:
    """Send a stock-alert email with a CSV attachment."""
    mail_user = os.getenv("MAIL_USERNAME", "")
    mail_pass = os.getenv("MAIL_PASSWORD", "")
    mail_from = os.getenv("MAIL_FROM", mail_user)
    mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    print(mail_user, mail_pass, mail_from, mail_server, mail_port)
    if not mail_user or not mail_pass:
        msg = f"MAIL_USERNAME / MAIL_PASSWORD not set – skipping email to {to_email}"
        logger.warning(msg)
        print(f"[scheduler] WARNING: {msg}")
        return

    subject = f"⚠️ WMS Stock Alert – {len(at_risk)} SKU(s) need replenishment"
    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")

    html_body = f"""
    <div style="font-family:Segoe UI,sans-serif;max-width:720px;margin:0 auto;color:#1a1a2e;">
      <div style="background:#1976d2;padding:24px 32px;border-radius:8px 8px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:1.4rem;">📦 WMS Stock Alert</h1>
        <p style="color:#bbdefb;margin:6px 0 0;">{now_str}</p>
      </div>
      <div style="background:#fff;padding:28px 32px;border:1px solid #e5e7eb;border-top:none;">
        <p style="font-size:1rem;">Hi <strong>{name}</strong>,</p>
        <p>The following <strong>{len(at_risk)} SKU(s)</strong> have reached or dropped below
        their reorder point and require replenishment:</p>
        {_build_html_table(at_risk)}
        <p style="margin-top:20px;">A full CSV of the at-risk items is attached for your records.</p>
        <p style="color:#6b7280;font-size:0.85rem;margin-top:32px;">
          This alert was generated automatically by your Warehouse Management System.<br>
          You can manage alert preferences in the <strong>Alerts</strong> tab.
        </p>
      </div>
    </div>"""

    msg = MIMEMultipart("mixed")
    mail_og_user = os.getenv("MAIL_USER", "")
    msg["From"]    = mail_og_user
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    # CSV attachment
    csv_bytes = _build_csv(at_risk)
    part = MIMEBase("application", "octet-stream")
    part.set_payload(csv_bytes)
    encoders.encode_base64(part)
    filename = f"at_risk_skus_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    with smtplib.SMTP(mail_server, mail_port) as server:
        server.ehlo()
        server.starttls()
        server.login(mail_user, mail_pass)
        server.sendmail(mail_og_user, to_email, msg.as_string())

    logger.info("Alert email sent to %s", to_email)
    print(f"[scheduler] Alert email sent to {to_email}")


# ── Alert job ─────────────────────────────────────────────────────────────────

async def run_stock_alert_job() -> None:
    """Check at-risk SKUs and email all subscribed users."""
    logger.info("[scheduler] Running stock alert job …")
    try:
        # Import here to avoid circular import (main.py imports scheduler.py)
        from main import compute_at_risk_skus
        at_risk = compute_at_risk_skus()
        if not at_risk:
            logger.info("[scheduler] All SKUs healthy – no alerts to send.")
            return

        users = get_all_users_with_alerts_enabled()
        if not users:
            logger.info("[scheduler] No users with alerts enabled.")
            return

        logger.info(
            "[scheduler] %d at-risk SKU(s), emailing %d user(s).",
            len(at_risk), len(users),
        )

        for user in users:
            try:
                send_alert_email(user["email"], user["name"], at_risk)
                update_last_alert_sent(user["id"])
            except Exception as e:
                logger.error("Failed to send alert to %s: %s", user["email"], e)

    except Exception as e:
        logger.error("[scheduler] Alert job error: %s", e)


# ── Scheduler factory ─────────────────────────────────────────────────────────

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_stock_alert_job,
        trigger="interval",
        hours=6,
        id="stock_alert",
        replace_existing=True,
    )
    return scheduler
