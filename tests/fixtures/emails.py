"""
20 realistic email fixtures: 10 legitimate, 10 phishing.
Each is a dict with: id, label (ground truth), text.
These are human-written; no real credentials or PII.
"""

FIXTURES = [
    # ── Legitimate emails (label="safe") ──────────────────────────────────────
    {
        "id": "leg_01",
        "label": "safe",
        "text": (
            "Hi Sarah,\n\n"
            "Just wanted to follow up on the Q3 report. "
            "Can you send over the updated figures by Thursday? "
            "We'll need them before the board meeting on Friday.\n\n"
            "Thanks,\nMark"
        ),
    },
    {
        "id": "leg_02",
        "label": "safe",
        "text": (
            "Dear Dr. Patel,\n\n"
            "Your appointment is confirmed for Monday, 14 October at 9:30 AM. "
            "Please bring a photo ID and your insurance card. "
            "If you need to cancel or reschedule, call us at least 24 hours in advance.\n\n"
            "Best regards,\nRiverside Medical Clinic"
        ),
    },
    {
        "id": "leg_03",
        "label": "safe",
        "text": (
            "Hey Tom,\n\n"
            "Are we still on for the hiking trip this weekend? "
            "The forecast looks clear on Saturday. "
            "Let me know if you want to carpool — I can pick you up at 7 AM.\n\n"
            "Cheers,\nAlex"
        ),
    },
    {
        "id": "leg_04",
        "label": "safe",
        "text": (
            "Hello,\n\n"
            "Your order #84521 has shipped and is on its way. "
            "Estimated delivery: 3-5 business days. "
            "You can track your package using the link below:\n"
            "https://track.example-logistics.com/84521\n\n"
            "Thank you for shopping with us!\nCustomer Support Team"
        ),
    },
    {
        "id": "leg_05",
        "label": "safe",
        "text": (
            "Hi team,\n\n"
            "Reminder that the all-hands meeting is this Thursday at 2 PM in Conference Room B. "
            "Please review the agenda that was shared last week. "
            "If you have topics to add, send them to me by Wednesday noon.\n\n"
            "See you there,\nOperations"
        ),
    },
    {
        "id": "leg_06",
        "label": "safe",
        "text": (
            "Dear James,\n\n"
            "Thank you for attending our webinar on sustainable investing. "
            "We've attached the slides and a recording link for your reference. "
            "Our next event is scheduled for November 5th — registration is now open.\n\n"
            "Best wishes,\nGreenFinance Events Team"
        ),
    },
    {
        "id": "leg_07",
        "label": "safe",
        "text": (
            "Hi,\n\n"
            "Your subscription renewal is coming up on 1 November. "
            "Your plan will auto-renew at $12.99/month unless you cancel before then. "
            "Manage your subscription at account.example.com/billing.\n\n"
            "Thanks for being a member!\nSupport"
        ),
    },
    {
        "id": "leg_08",
        "label": "safe",
        "text": (
            "Good morning Professor Chen,\n\n"
            "I am writing to request an extension on the term paper due 20 October. "
            "I have been dealing with a family emergency and have documentation from student services. "
            "Would an extension until 27 October be possible?\n\n"
            "Sincerely,\nEmma Larsson"
        ),
    },
    {
        "id": "leg_09",
        "label": "safe",
        "text": (
            "Hi Lisa,\n\n"
            "The invoice for October services is attached (Invoice #2024-089, $3,450.00). "
            "Payment is due within 30 days. "
            "Please remit via bank transfer to the account details on the invoice. "
            "Let me know if you have any questions.\n\n"
            "Best,\nFreelance Studio"
        ),
    },
    {
        "id": "leg_10",
        "label": "safe",
        "text": (
            "Hello,\n\n"
            "We noticed you haven't logged in for a while. "
            "Your account is still active. "
            "If you'd like to close it, visit your settings page at any time. "
            "We're here if you need help.\n\n"
            "The Support Team"
        ),
    },
    # ── Phishing emails (label="phishing") ────────────────────────────────────
    {
        "id": "phi_01",
        "label": "phishing",
        "text": (
            "URGENT: Your account has been suspended!\n\n"
            "Dear Customer,\n\n"
            "We detected suspicious activity on your account. "
            "Your access has been temporarily suspended for your security. "
            "To restore access, verify your identity immediately by clicking the link below:\n\n"
            "http://secure-account-verify.xyz/restore?token=a7f3e\n\n"
            "Failure to verify within 24 hours will result in permanent account closure.\n\n"
            "Security Team — Online Banking"
        ),
    },
    {
        "id": "phi_02",
        "label": "phishing",
        "text": (
            "Subject: You have won a $1,000 Amazon Gift Card!\n\n"
            "Congratulations! You have been selected as today's lucky winner. "
            "Click the link below to claim your $1,000 gift card before it expires in 2 hours:\n\n"
            "http://amazоn-prize-claim.net/claim?user=selected\n\n"
            "Note: You must provide your name, address, and card details to complete delivery."
        ),
    },
    {
        "id": "phi_03",
        "label": "phishing",
        "text": (
            "From: IT-Helpdesk <it-support@company-helpdesk.ru>\n\n"
            "Dear Employee,\n\n"
            "Your corporate email password will expire in 12 hours. "
            "To prevent losing access to your work email, reset your password now:\n\n"
            "http://company-intranet-passwordreset.com/reset\n\n"
            "If you do not reset, your account will be deactivated automatically.\n\n"
            "IT Department"
        ),
    },
    {
        "id": "phi_04",
        "label": "phishing",
        "text": (
            "Dear PayPal User,\n\n"
            "We noticed an unusual sign-in attempt from Romania (IP: 185.220.101.12). "
            "If this wasn't you, please confirm your account details immediately to prevent unauthorised access:\n\n"
            "https://paypal.com.verify-login.net/confirm\n\n"
            "Provide your full name, date of birth, and card number to complete verification.\n\n"
            "PayPal Security"
        ),
    },
    {
        "id": "phi_05",
        "label": "phishing",
        "text": (
            "Hi,\n\n"
            "Your invoice #INV-00923 for $4,899.00 is attached. "
            "Please review and approve the wire transfer by end of day. "
            "Use the banking details updated in our system last week.\n\n"
            "If you have questions, reply to this email or call +1-800-555-9823.\n\n"
            "Accounts Receivable"
        ),
    },
    {
        "id": "phi_06",
        "label": "phishing",
        "text": (
            "FINAL NOTICE: Action Required on Your Netflix Account\n\n"
            "Your Netflix membership has been put on hold because we're having trouble with your current billing information. "
            "To keep your membership, update your payment info here:\n\n"
            "http://netflix-billing-update.com/account/billing\n\n"
            "If you do not update within 48 hours, your account will be cancelled and you'll lose your viewing history."
        ),
    },
    {
        "id": "phi_07",
        "label": "phishing",
        "text": (
            "Dear Sir/Madam,\n\n"
            "I am Dr. Emmanuel Okafor, an attorney in Lagos, Nigeria. "
            "My late client, who shares your surname, passed away without a will. "
            "I require a trusted foreign partner to claim the $12.5 million estate. "
            "Reply with your full name, address, and bank details to proceed.\n\n"
            "Strictly Confidential."
        ),
    },
    {
        "id": "phi_08",
        "label": "phishing",
        "text": (
            "Important: Your Apple ID has been used to sign in to iCloud on a new iPhone 15.\n\n"
            "If you authorised this, ignore this message.\n"
            "If not, your account may be compromised. Verify now at:\n\n"
            "http://apple-id-verify.support/verify-account\n\n"
            "Enter your Apple ID and password to secure your account immediately."
        ),
    },
    {
        "id": "phi_09",
        "label": "phishing",
        "text": (
            "MICROSOFT SECURITY ALERT\n\n"
            "Your Microsoft 365 account has been flagged for suspicious login activity. "
            "Your password will be reset in 1 hour unless you confirm your identity.\n\n"
            "Click here to verify: http://microsoft365-security.info/verify\n\n"
            "You must enter your current password and mobile number to prevent lockout."
        ),
    },
    {
        "id": "phi_10",
        "label": "phishing",
        "text": (
            "Dear Valued Customer,\n\n"
            "A package from DHL could not be delivered due to an incomplete address. "
            "To reschedule delivery, pay the small holding fee of $2.99 here:\n\n"
            "http://dhl-redelivery-fee.com/pay?ref=PKG8842\n\n"
            "Without payment within 3 days, the package will be returned to sender."
        ),
    },
]

__all__ = ["FIXTURES"]
