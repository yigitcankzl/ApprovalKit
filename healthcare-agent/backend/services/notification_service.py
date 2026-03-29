"""
Notification Service — Handles all outbound communications via ApprovalKit Token Vault.
Gmail, Slack, Google Calendar, Google Drive.
"""
import logging
from backend.services.approval_gateway import ApprovalGateway, ApprovalDenied

logger = logging.getLogger("healthcare.notifications")


class NotificationService:

    @staticmethod
    async def notify_doctor_new_patient(doctor_email: str, doctor_name: str, patient_name: str, patient_mrn: str):
        try:
            result = await ApprovalGateway.send_email(
                recipient=doctor_email,
                subject=f"New Patient Assigned: {patient_name} ({patient_mrn})",
                body=(
                    f"Dear Dr. {doctor_name},\n\n"
                    f"A new patient has been assigned to your care:\n"
                    f"- Name: {patient_name}\n"
                    f"- MRN: {patient_mrn}\n\n"
                    f"Please review the patient's records at your earliest convenience.\n\n"
                    f"— MedCore Healthcare Agent"
                ),
                email_type="patient_assignment",
            )
            logger.info(f"Doctor notification sent to {doctor_email}")
            return result
        except ApprovalDenied as e:
            logger.warning(f"Doctor notification denied: {e.status}")
            return {"status": "notification_denied", "reason": e.status}

    @staticmethod
    async def announce_intake(patient_name: str, patient_mrn: str, doctor_name: str, conditions: list[str]):
        try:
            conditions_str = ", ".join(conditions) if conditions else "None listed"
            result = await ApprovalGateway.send_slack_message(
                channel="#intake",
                message=(
                    f"🏥 *New Patient Intake*\n"
                    f"• Patient: {patient_name} ({patient_mrn})\n"
                    f"• Assigned to: Dr. {doctor_name}\n"
                    f"• Conditions: {conditions_str}\n"
                    f"• Status: Onboarding in progress"
                ),
            )
            logger.info(f"Intake announced for {patient_mrn}")
            return result
        except ApprovalDenied as e:
            logger.warning(f"Slack announcement denied: {e.status}")
            return {"status": "notification_denied", "reason": e.status}

    @staticmethod
    async def schedule_first_appointment(
        patient_name: str, doctor_name: str, doctor_email: str,
        patient_email: str, start_time: str, end_time: str,
    ):
        try:
            result = await ApprovalGateway.create_calendar_event(
                title=f"Initial Consultation — {patient_name}",
                start_time=start_time,
                end_time=end_time,
                attendees=[doctor_email, patient_email],
                location="MedCore General Hospital, Main Building",
            )
            logger.info(f"First appointment scheduled for {patient_name}")
            return result
        except ApprovalDenied as e:
            logger.warning(f"Calendar event denied: {e.status}")
            return {"status": "notification_denied", "reason": e.status}

    @staticmethod
    async def notify_pharmacy(pharmacy_email: str, patient_name: str, patient_mrn: str,
                              medication: str, dosage: str, quantity: int, doctor_name: str):
        try:
            result = await ApprovalGateway.send_email(
                recipient=pharmacy_email,
                subject=f"New Prescription — {patient_name} ({patient_mrn})",
                body=(
                    f"New prescription approved:\n\n"
                    f"Patient: {patient_name} ({patient_mrn})\n"
                    f"Medication: {medication} {dosage}\n"
                    f"Quantity: {quantity}\n"
                    f"Prescribing Physician: Dr. {doctor_name}\n\n"
                    f"Please prepare for pickup/delivery.\n\n"
                    f"— MedCore Healthcare Agent"
                ),
                email_type="prescription",
            )
            return result
        except ApprovalDenied as e:
            return {"status": "notification_denied", "reason": e.status}

    @staticmethod
    async def notify_patient_dose_change(patient_email: str, patient_name: str,
                                          medication: str, old_dose: str, new_dose: str):
        try:
            return await ApprovalGateway.send_email(
                recipient=patient_email,
                subject=f"Prescription Update — {medication}",
                body=(
                    f"Dear {patient_name},\n\n"
                    f"Your prescription for {medication} has been updated:\n"
                    f"• Previous dosage: {old_dose}\n"
                    f"• New dosage: {new_dose}\n\n"
                    f"Please contact your doctor if you have any questions.\n\n"
                    f"— MedCore General Hospital"
                ),
                email_type="dose_change",
            )
        except ApprovalDenied:
            return {"status": "notification_denied"}

    @staticmethod
    async def share_patient_records(patient_name: str, patient_mrn: str,
                                     recipient_email: str, data_scope: str):
        try:
            file_name = (
                f"{patient_mrn}_{patient_name.replace(' ', '_')}_"
                f"{'full_records' if data_scope == 'full' else 'summary'}.pdf"
            )
            return await ApprovalGateway.share_drive_file(
                file_name=file_name,
                recipient_email=recipient_email,
                access_level="reader",
                folder=f"Patient Records/{patient_mrn}",
            )
        except ApprovalDenied:
            return {"status": "share_denied"}

    @staticmethod
    async def notify_referral_clinic(clinic_email: str, patient_name: str, reason: str):
        try:
            return await ApprovalGateway.send_email(
                recipient=clinic_email,
                subject=f"Patient Referral — {patient_name}",
                body=(
                    f"Dear Colleagues,\n\n"
                    f"We are referring patient {patient_name} to your facility.\n"
                    f"Reason: {reason}\n\n"
                    f"Patient records have been shared via Google Drive.\n"
                    f"Please review and contact us for coordination.\n\n"
                    f"— MedCore General Hospital"
                ),
                email_type="referral",
            )
        except ApprovalDenied:
            return {"status": "notification_denied"}

    @staticmethod
    async def alert_emergency(patient_name: str, patient_mrn: str, reason: str, event_type: str):
        channel = "#emergency" if event_type == "data_access" else "#security"
        emoji = "🚨" if event_type == "security_breach" else "����"
        try:
            return await ApprovalGateway.send_slack_message(
                channel=channel,
                message=(
                    f"{emoji} *EMERGENCY — {event_type.upper().replace('_', ' ')}*\n"
                    f"• Patient: {patient_name} ({patient_mrn})\n"
                    f"• Reason: {reason}\n"
                    f"• Status: Immediate attention required"
                ),
            )
        except ApprovalDenied:
            return {"status": "alert_denied"}

    @staticmethod
    async def alert_billing(invoice_number: str, amount: float, description: str, channel: str = "#billing"):
        try:
            return await ApprovalGateway.send_slack_message(
                channel=channel,
                message=(
                    f"💰 *Billing Alert*\n"
                    f"• Invoice: {invoice_number}\n"
                    f"• Amount: ${amount:,.2f}\n"
                    f"• Description: {description}"
                ),
            )
        except ApprovalDenied:
            return {"status": "alert_denied"}

    @staticmethod
    async def notify_delegation(
        doctor_name: str, delegate_name: str, start_date: str, end_date: str,
        patient_emails: list[str],
    ):
        for email in patient_emails[:20]:
            try:
                await ApprovalGateway.send_email(
                    recipient=email,
                    subject=f"Physician Coverage Update — Dr. {doctor_name}",
                    body=(
                        f"Dear Patient,\n\n"
                        f"Dr. {doctor_name} will be on leave from {start_date} to {end_date}.\n"
                        f"During this period, Dr. {delegate_name} will be your covering physician.\n\n"
                        f"For urgent matters, please contact our main line.\n\n"
                        f"— MedCore General Hospital"
                    ),
                    email_type="delegation",
                )
            except ApprovalDenied:
                continue

    @staticmethod
    async def welcome_new_staff(staff_email: str, staff_name: str, role: str):
        try:
            return await ApprovalGateway.send_email(
                recipient=staff_email,
                subject=f"Welcome to MedCore General Hospital",
                body=(
                    f"Dear {staff_name},\n\n"
                    f"Welcome to MedCore General Hospital! Your role: {role}\n\n"
                    f"Your system access has been configured. Please complete\n"
                    f"the onboarding checklist in your employee portal.\n\n"
                    f"— MedCore HR Department"
                ),
                email_type="onboarding",
            )
        except ApprovalDenied:
            return {"status": "notification_denied"}
