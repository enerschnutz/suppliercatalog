import frappe
from frappe.contacts.doctype.contact.contact import get_default_contact
from frappe.email.doctype.email_template.email_template import get_email_template
from frappe.core.doctype.communication.email import make as make_communication
from email.header import Header
from email.utils import formataddr


# ----------------------------------------------------------
# Send Single Sales Invoice
# ----------------------------------------------------------

@frappe.whitelist()
def send_sales_invoice_email(invoice_name, template_name):

    doc = frappe.get_doc("Sales Invoice", invoice_name)

    if doc.docstatus != 1:
        frappe.throw(f"Sales Invoice {doc.name} is not submitted.")

    # Render template
    context = doc.as_dict()
    context["doc"] = doc

    email_template = get_email_template(template_name, context)

    subject = email_template.get("subject")
    message = email_template.get("message")

    if not subject:
        frappe.throw(f"Rendered subject is empty for Invoice {doc.name}")

    # -----------------------------
    # ORIGINAL WORKING RECIPIENT LOGIC
    # -----------------------------

    email = None

    if getattr(doc, "custom_email", None):
        email = doc.custom_email

    if not email:
        contact_name = get_default_contact("Customer", doc.customer)

        if contact_name:
            contact = frappe.get_doc("Contact", contact_name)
            for row in contact.email_ids:
                if row.email_id:
                    email = row.email_id
                    break

    if not email:
        address_links = frappe.get_all(
            "Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": doc.customer,
                "parenttype": "Address"
            },
            fields=["parent"]
        )

        for link in address_links:
            address_doc = frappe.get_doc("Address", link.parent)
            if address_doc.email_id:
                email = address_doc.email_id
                break

    if not email:
        frappe.throw(f"No email address found for Invoice {doc.name}.")

    # -----------------------------
    # Attach PDF (standard)
    # -----------------------------

    attachment = frappe.attach_print(
        "Sales Invoice",
        doc.name,
        file_name=doc.name
    )

    # -----------------------------
    # USE FRAPPE INTERNAL EMAIL PIPELINE
    # -----------------------------
    
    # Get company document
    company_doc = frappe.get_doc("Company", doc.company)
    sender_name = company_doc.company_name

    # Get default outgoing email account
    sender_email = frappe.get_value(
        "Email Account",
        {"default_outgoing": 1},
        "email_id"
    )

    if not sender_email:
        frappe.throw("No default outgoing Email Account configured.")

    sender = f"{doc.company} <{sender_email}>"

    make_communication(
        doctype="Sales Invoice",
        name=doc.name,
        subject=subject,
        content=message,
        recipients=email,
        sender=sender,
        send_email=1,
        attachments=[attachment]
    )

    return True

# ----------------------------------------------------------
# Background Enqueue
# ----------------------------------------------------------

@frappe.whitelist()
def enqueue_bulk_sales_invoice_email(invoice_names, template_name):

    if isinstance(invoice_names, str):
        invoice_names = frappe.parse_json(invoice_names)

    user = frappe.session.user

    frappe.enqueue(
        method="suppliercatalog.german_accounting.utils.quick_mail.process_bulk_sales_invoice_email",
        queue="default",
        timeout=600,
        invoice_names=invoice_names,
        template_name=template_name,
        user=user
    )

    return "Job queued"


# ----------------------------------------------------------
# Background Worker
# ----------------------------------------------------------

def process_bulk_sales_invoice_email(invoice_names, template_name, user):

    total = len(invoice_names)
    success_count = 0
    failed_docs = []

    for i, name in enumerate(invoice_names, start=1):

        try:
            send_sales_invoice_email(name, template_name)
            success_count += 1

        except Exception:
            failed_docs.append(name)
            frappe.log_error(
                title=f"Bulk Email Failed for {name}",
                message=frappe.get_traceback()
            )

        frappe.publish_realtime(
            event="bulk_email_progress",
            message={
                "current": i,
                "total": total
            },
            user=user
        )

    frappe.publish_realtime(
        event="bulk_email_done",
        message={
            "success_count": success_count,
            "total": total,
            "failed_docs": failed_docs
        },
        user=user
    )

# ----------------------------------------------------------
# Preview
# ----------------------------------------------------------

@frappe.whitelist()
def preview_sales_invoice_template(invoice_name, template_name):

    doc = frappe.get_doc("Sales Invoice", invoice_name)

    context = doc.as_dict()
    context["doc"] = doc

    email_template = get_email_template(template_name, context)

    return {
        "subject": email_template.get("subject"),
        "message": email_template.get("message")
    }