import frappe
from frappe import _

def sync_posting_date_with_bill_date(doc, method):
    if doc.bill_date:
        doc.posting_date = doc.bill_date

    if doc.bill_date and doc.posting_date != doc.bill_date:
        frappe.throw(_("Posting Date must match Bill Date."))
