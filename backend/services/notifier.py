"""Notification Service - Sends approval requests via email and Slack."""
import structlog
from typing import Any
import httpx

log = structlog.get_logger(__name__)


async def send_approval_notification(
    change_type: str,
    title: str,
    description: str,
    diff_data: dict[str, Any],
    approval_url: str,
    config: dict[str, str] | None = None
) -> bool:
    """
    Send notification about pending changes awaiting approval.

    Args:
        change_type: Type of change (db_schema, business_knowledge)
        title: Brief title of the change
        description: Detailed description
        diff_data: The actual diff/changes
        approval_url: URL to the approval page
        config: Dict with smtp_host, smtp_user, smtp_password, slack_webhook_url

    Returns:
        bool: True if notification sent successfully
    """
    if not config:
        log.warning("notifier.no_config", change_type=change_type)
        return False

    success = True

    # Send email notification
    if config.get("smtp_user") and config.get("smtp_password"):
        try:
            await _send_email(
                to_email=config.get("notification_email", config["smtp_user"]),
                subject=f"[Analytics Copilot] Approval Required: {title}",
                body=_format_email_body(change_type, title, description, diff_data, approval_url),
                config=config
            )
            log.info("notifier.email_sent", title=title)
        except Exception as e:
            log.error("notifier.email_failed", error=str(e))
            success = False

    # Send Slack notification
    if config.get("slack_webhook_url"):
        try:
            await _send_slack(
                webhook_url=config["slack_webhook_url"],
                title=title,
                description=description,
                approval_url=approval_url
            )
            log.info("notifier.slack_sent", title=title)
        except Exception as e:
            log.error("notifier.slack_failed", error=str(e))
            success = False

    return success


async def _send_email(to_email: str, subject: str, body: str, config: dict[str, str]) -> None:
    """Send email notification."""
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config["smtp_user"]
    msg["To"] = to_email
    msg.set_content(body)

    smtp_host = config.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(config.get("smtp_port", "587"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(config["smtp_user"], config["smtp_password"])
        server.send_message(msg)


async def _send_slack(webhook_url: str, title: str, description: str, approval_url: str) -> None:
    """Send Slack notification."""
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={
            "text": f"🔔 Analytics Copilot: Approval Required",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{title}*\n{description}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Review Changes"
                            },
                            "url": approval_url,
                            "style": "primary"
                        }
                    ]
                }
            ]
        })


def _format_email_body(
    change_type: str,
    title: str,
    description: str,
    diff_data: dict[str, Any],
    approval_url: str
) -> str:
    """Format the email body."""
    return f"""
Analytics Copilot - Document Update Approval Required
{'=' * 60}

Change Type: {change_type}
Title: {title}

Description:
{description}

Changes:
{diff_data.get('summary', 'No summary available')}

Please review and approve or reject these changes at:
{approval_url}

{'=' * 60}
This is an automated message from Analytics Copilot.
"""
