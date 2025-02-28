# aquanova_suite/hooks.py

doc_events = {
    "Wastewater System Design": {
        "on_submit": [
            "aquanova_suite.customizations.create_production_order",
            "aquanova_suite.customizations.send_design_approval_email",
            "aquanova_suite.customizations.attach_design_pdf"
        ]
    },
    "Production Order": {
        "on_submit": "aquanova_suite.customizations.create_installation_record"
    },
    "Installation Record": {
        "on_submit": "aquanova_suite.customizations.create_warranty_record"
    },
    "Maintenance Log": {
        "on_submit": "aquanova_suite.customizations.log_maintenance_activity"
    },
    "Manufactured Component": {
        "on_submit": "aquanova_suite.customizations.update_inventory_on_component_production"
    }
}
