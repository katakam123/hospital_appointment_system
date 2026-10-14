from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_prescription_pdf(
    patient_name: str,
    doctor_name: str,
    appointment_number: str,
    diagnosis: str,
    prescription: str,
    advice: str = "",
    follow_up_date: str = "",
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 60

    pdf.setTitle("Medical Prescription")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "Medical Prescription")
    y -= 40

    pdf.setFont("Helvetica", 11)

    fields = [
        ("Patient", patient_name),
        ("Doctor", doctor_name),
        ("Appointment number", appointment_number),
        ("Diagnosis", diagnosis),
        ("Prescription", prescription),
        ("Advice", advice or "Not provided"),
        ("Follow-up date", follow_up_date or "Not scheduled"),
    ]

    for label, value in fields:
        text = f"{label}: {value}"
        # Basic wrapping for long fields.
        words = text.split()
        lines = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()
            if pdf.stringWidth(candidate, "Helvetica", 11) > width - 100:
                lines.append(current)
                current = word
            else:
                current = candidate

        if current:
            lines.append(current)

        for line in lines:
            if y < 60:
                pdf.showPage()
                pdf.setFont("Helvetica", 11)
                y = height - 60

            pdf.drawString(50, y, line)
            y -= 18

        y -= 8

    pdf.save()
    return buffer.getvalue()