import frappe
from frappe.utils import nowdate, add_years, add_months, getdate
from frappe.utils.pdf import get_pdf

def create_production_order(doc, method):
    """
    Create a Production Order automatically when a Wastewater System Design is approved.
    """
    try:
        if doc.status == "Approved":
            production_order = frappe.get_doc({
                "doctype": "Production Order",
                "production_order_id": doc.design_id,  # Using design_id as a reference
                "wastewater_design": doc.name,
                "status": "Draft",
                "expected_start_date": nowdate(),
                "production_qty": 1,  # Modify as per requirement
                "bom_no": doc.get("bom_reference")  # Optional: BOM reference field
            })
            production_order.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.msgprint(f"Production Order {production_order.name} created for Design {doc.design_id}")
    except Exception as e:
        frappe.log_error(message=str(e), title="Production Order Creation Failed")
        frappe.throw("Failed to create Production Order. Please check the system logs.")

def send_design_approval_email(doc, method):
    """
    Send an email notification to all Production Managers when a design is approved.
    """
    try:
        subject = f"Design Approved: {doc.design_id}"
        message = f"Design {doc.design_id} approved on {doc.design_date}. Please review the production details in ERPNext."
        
        # Retrieve emails of users having the "Production Manager" role.
        production_managers = frappe.get_all("Has Role", filters={"role": "Production Manager"}, fields=["parent"])
        recipients = []
        for pm in production_managers:
            user_email = frappe.db.get_value("User", pm.parent, "email")
            if user_email:
                recipients.append(user_email)
        
        if recipients:
            frappe.sendmail(recipients=recipients, subject=subject, message=message)
    except Exception as e:
        frappe.log_error(message=str(e), title="Design Approval Email Failed")
        frappe.throw("Failed to send email notification. Please check the system logs.")

def attach_design_pdf(doc, method):
    """
    Automatically generate a PDF from the design record and attach it.
    """
    try:
        html = frappe.render_template("aquanova_suite/templates/print/wastewater_design.html", {"doc": doc})
        pdf_data = get_pdf(html)
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"{doc.design_id}.pdf",
            "is_private": 1,
            "content": pdf_data,
            "attached_to_doctype": doc.doctype,
            "attached_to_name": doc.name
        })
        file_doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(message=str(e), title="PDF Generation Failed")
        frappe.throw("Failed to generate PDF. Please check the system logs.")

def create_installation_record(doc, method):
    """
    Create an Installation Record when a Production Order is completed.
    Also triggers creation of the maintenance schedule (job cards).
    """
    try:
        # Only create an installation record if not already linked.
        if doc.status == "Completed" and not doc.get("installation_record"):
            installation = frappe.get_doc({
                "doctype": "Installation Record",
                "production_order": doc.name,
                "system_design": doc.get("wastewater_design"),
                "installation_date": nowdate(),
                "installed_by": frappe.session.user,
                "status": "Scheduled"
            })
            installation.insert(ignore_permissions=True)
            doc.db_set("installation_record", installation.name)
            frappe.db.commit()
            frappe.msgprint(f"Installation Record {installation.name} created for Production Order {doc.name}")
            # Automatically generate a quarterly maintenance schedule (job cards)
            create_maintenance_schedule(installation)
    except Exception as e:
        frappe.log_error(message=str(e), title="Installation Record Creation Failed")
        frappe.throw("Failed to create Installation Record. Please check the system logs.")

def create_warranty_record(doc, method):
    """
    Create a Warranty Record automatically when an Installation Record is marked as 'Installed'.
    """
    try:
        if doc.status == "Installed":
            warranty_end_date = add_years(doc.installation_date, 1)
            warranty = frappe.get_doc({
                "doctype": "Warranty Record",
                "installation_record": doc.name,
                "start_date": doc.installation_date,
                "end_date": warranty_end_date,
                "status": "Active",
                "remarks": "Warranty automatically generated upon installation."
            })
            warranty.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.msgprint(f"Warranty Record {warranty.name} created for Installation Record {doc.name}")
    except Exception as e:
        frappe.log_error(message=str(e), title="Warranty Record Creation Failed")
        frappe.throw("Failed to create Warranty Record. Please check the system logs.")

def create_maintenance_schedule(installation_doc):
    """
    Generate a maintenance schedule by creating Job Cards for scheduled maintenance.
    Here, we create quarterly job cards over a 1-year warranty period.
    """
    try:
        install_date = getdate(installation_doc.installation_date)
        # Define maintenance intervals (in months); for quarterly: 3, 6, 9, and 12 months.
        schedule_intervals = [3, 6, 9, 12]
        for months in schedule_intervals:
            scheduled_date = add_months(install_date, months)
            # Create a job card for each scheduled maintenance date.
            create_job_card(installation_doc, scheduled_date, maintenance_type="Scheduled Maintenance")
    except Exception as e:
        frappe.log_error(message=str(e), title="Maintenance Schedule Creation Failed")
        frappe.throw("Failed to create Maintenance Schedule. Please check the system logs.")

def create_job_card(installation_doc, scheduled_date, maintenance_type="Scheduled Maintenance", emergency=False):
    """
    Create a Job Card for maintenance tasks.
    Assumes a custom DocType 'Job Card' exists with required fields.
    """
    try:
        job_card = frappe.get_doc({
            "doctype": "Job Card",
            "job_card_id": f"JC-{installation_doc.name}-{scheduled_date}",
            "installation_record": installation_doc.name,
            "scheduled_date": scheduled_date,
            "maintenance_type": maintenance_type,
            "status": "Open",
            "emergency": emergency,
            "remarks": "Auto-generated job card" if not emergency else "Emergency job card generated"
        })
        job_card.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Job Card {job_card.name} created for Installation {installation_doc.name} on {scheduled_date}")
    except Exception as e:
        frappe.log_error(message=str(e), title="Job Card Creation Failed")
        frappe.throw("Failed to create Job Card. Please check the system logs.")

def handle_emergency_job_card(installation_record, details=""):
    """
    Create an emergency Job Card manually for urgent maintenance.
    """
    try:
        scheduled_date = nowdate()
        create_job_card(installation_record, scheduled_date, maintenance_type="Emergency Maintenance", emergency=True)
        frappe.msgprint("Emergency Job Card created.")
    except Exception as e:
        frappe.log_error(message=str(e), title="Emergency Job Card Creation Failed")
        frappe.throw("Failed to create Emergency Job Card. Please check the system logs.")

def log_maintenance_activity(doc, method):
    """
    Log maintenance activity for an installation or equipment.
    """
    try:
        maintenance_log = frappe.get_doc({
            "doctype": "Maintenance Log",
            "maintenance_id": doc.get("maintenance_id") or f"ML-{frappe.generate_hash()}",
            "installation_record": doc.get("installation_record", ""),
            "equipment": doc.get("equipment"),
            "maintenance_date": nowdate(),
            "performed_by": frappe.session.user,
            "activity": doc.get("activity", "Routine Check"),
            "remarks": doc.get("remarks", "")
        })
        maintenance_log.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Maintenance Log {maintenance_log.name} created.")
    except Exception as e:
        frappe.log_error(message=str(e), title="Maintenance Log Creation Failed")
        frappe.throw("Failed to log maintenance activity. Please check the system logs.")

def update_inventory_on_component_production(doc, method):
    """
    Update inventory when a Manufactured Component is recorded.
    Extend this function to integrate with your inventory management system.
    """
    try:
        frappe.msgprint(f"Inventory updated for Manufactured Component: {doc.component_id}")
    except Exception as e:
        frappe.log_error(message=str(e), title="Inventory Update Failed")
        frappe.throw("Failed to update inventory. Please check the system logs.")

def generate_maintenance_report():
    """
    Generate a monthly maintenance report and email it to the maintenance team.
    """
    try:
        report_html = frappe.render_template("aquanova_suite/templates/print/maintenance_report.html", {})
        pdf_data = get_pdf(report_html)
        
        subject = "Monthly Maintenance Report"
        message = "Please find attached the monthly maintenance report."
        
        frappe.sendmail(
            recipients=["maintenance@example.com"],
            subject=subject,
            message=message,
            attachments=[{
                "fname": "Maintenance_Report.pdf",
                "fcontent": pdf_data
            }]
        )
    except Exception as e:
        frappe.log_error(message=str(e), title="Maintenance Report Generation Failed")

