import frappe
from frappe import _
import qrcode
import io
import base64


def get_epc_bank_account(doc,methode):

    settings = frappe.get_single("German Accounting Settings")

    # Do nothing if EPC is disabled
    if not settings.epc_qr_enabled:
        return

    # If user already selected a bank account → do not overwrite
    if doc.custom_recipient_bankaccount:
        return

    # Fallback to settings default and write it into the document
    if settings.epc_bank_acc:
        doc.custom_recipient_bankaccount = settings.epc_bank_acc
        return

    # Nothing configured → throw error
    frappe.throw(
        _("EPC Bank Account is not configured.")
        + "<br><br>"
        + '<a href="/app/german-accounting-settings">'
        + _("Open German Accounting Settings")
        + "</a>"
    )
    return


def generate_epc_payload(doc):

    settings = frappe.get_single("German Accounting Settings")

    # Do nothing if EPC is disabled
    if not settings.epc_qr_enabled:
        return None
    
    # Get recipient if diffrent
    recipient = settings.bank_recipient_name
    if not recipient:
        recipient = doc.company

    bank_account_name = doc.custom_recipient_bankaccount
    if not bank_account_name:
        return None

    bank_account = frappe.get_doc("Bank Account", bank_account_name)

    iban = bank_account.iban
    if not iban:
        frappe.throw(_("IBAN is missing in selected EPC Bank Account."))

    # Get linked Bank document (for BIC)
    bic = ""
    if bank_account.bank:
        bank_doc = frappe.get_doc("Bank", bank_account.bank)
        bic = bank_doc.swift_number or ""

    amount = f"{doc.grand_total:.2f}"

    posting_date = frappe.utils.formatdate(doc.posting_date, "dd.MM.yyyy")

    purpose = f"{doc.name}, {doc.customer}, {posting_date}"
    purpose = purpose[:140]

    payload = "\n".join([
        "BCD",
        "002",
        "1",
        "SCT",
        bic,
        recipient,
        iban.replace(" ", ""),
        f"EUR{amount}",
        "",
        purpose
    ])

    return payload


def generate_epc_qr_base64(doc):

    payload = generate_epc_payload(doc)
    if not payload:
        return ""

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )

    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    return base64.b64encode(buffer.getvalue()).decode()


def add_epc_qr(doc, method):

    if doc.docstatus != 1:
        return

    qr_base64 = generate_epc_qr_base64(doc)

    if qr_base64:
        doc.db_set(
            "custom_epc_qr_code",
            f'<img src="data:image/png;base64,{qr_base64}" width="150">',
            update_modified=False
        )