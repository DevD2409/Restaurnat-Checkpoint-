"""
Transactional Email Service for Smart Restaurant Management Platform (SRMP)
Supports Resend API with explicit production kill-switch until verified sending domain is active.
"""

import logging
from typing import Optional, Dict, Any, List
import requests
from app.core.config import settings

logger = logging.getLogger("srmp.email")


class EmailService:
    def __init__(self):
        self.api_key = settings.RESEND_API_KEY
        self.from_email = settings.RESEND_FROM_EMAIL
        self.enabled = settings.ENABLE_TRANSACTIONAL_EMAIL and bool(self.api_key)

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends transactional email via Resend or logs simulation if disabled.
        """
        if not self.enabled:
            logger.info(
                f"[EMAIL SIMULATION - DISABLED PENDING VERIFIED DOMAIN] "
                f"To: {to_email} | Subject: '{subject}' | From: {self.from_email}"
            )
            return {
                "status": "simulated",
                "delivered": False,
                "reason": "Transactional email disabled pending verified sending domain.",
                "to": to_email,
                "subject": subject
            }

        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        if text_content:
            payload["text"] = text_content

        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=10
            )
            if resp.status_code in [200, 201]:
                data = resp.json()
                logger.info(f"Email sent successfully to {to_email} via Resend. ID: {data.get('id')}")
                return {"status": "sent", "delivered": True, "resend_id": data.get("id")}
            else:
                logger.error(f"Resend API error ({resp.status_code}): {resp.text}")
                return {"status": "failed", "delivered": False, "error": resp.text}
        except Exception as e:
            logger.error(f"Failed to transmit email to {to_email}: {e}")
            return {"status": "error", "delivered": False, "error": str(e)}

    def send_subscription_receipt(
        self,
        to_email: str,
        restaurant_name: str,
        plan_name: str,
        amount_inr: float,
        invoice_number: str
    ) -> Dict[str, Any]:
        subject = f"Invoice & Payment Receipt: {plan_name} Plan - {restaurant_name}"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2>Payment Receipt - Smart Restaurant Management Platform</h2>
            <p>Dear {restaurant_name} Team,</p>
            <p>Your subscription payment has been verified and settled successfully.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Invoice Number:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{invoice_number}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Plan:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{plan_name}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Amount Paid:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">₹{amount_inr:,.2f}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">PAID / ACTIVE</td></tr>
            </table>
            <p>Thank you for partnering with SRMP!</p>
        </div>
        """
        return self.send_email(to_email=to_email, subject=subject, html_content=html)

    def send_staff_invitation(
        self,
        to_email: str,
        staff_name: str,
        restaurant_name: str,
        username: str,
        temp_password: str
    ) -> Dict[str, Any]:
        subject = f"You've been invited to join {restaurant_name} on SRMP"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2>Welcome to {restaurant_name}</h2>
            <p>Hello {staff_name},</p>
            <p>Your staff portal account has been provisioned.</p>
            <p><strong>Username:</strong> {username}<br>
            <strong>Temporary Password:</strong> {temp_password}</p>
            <p><em>You will be required to change your password on first login.</em></p>
        </div>
        """
        return self.send_email(to_email=to_email, subject=subject, html_content=html)


email_service = EmailService()
