"""Seed closing macros into the database."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db_manager

macros = [
    {
        "name": "Closing - Standard",
        "category": "Closing",
        "content": (
            "Dear {customer_name} @ {company},\n\n"
            "Is there anything else we can assist you with?\n\n"
            "If there are no further questions at this time, I'll proceed to close this chat.\n\n"
            "However, please feel free to reopen it anytime if the issue hasn't been fully resolved, "
            "I'll be happy to continue supporting you.\n\n"
            "Thank you for contacting Edgeworks Solutions Support. Have a nice day!"
        ),
    },
    {
        "name": "Closing - Warm Follow-up",
        "category": "Closing",
        "content": (
            "Dear {customer_name} @ {company},\n\n"
            "If you have any further questions or concerns, please don't hesitate to reach out.\n\n"
            "We are here to help and want to ensure you're completely satisfied with our service.\n\n"
            "Thank you once again for your time and understanding. "
            "We truly value your business and look forward to continuing to support you."
        ),
    },
    {
        "name": "Closing - Quick Resolved",
        "category": "Closing",
        "content": (
            "Dear {customer_name} @ {company},\n\n"
            "Glad we could help! If you experience any further issues, don't hesitate to reach out.\n\n"
            "Thank you for contacting Edgeworks Solutions Support. Have a great day! \U0001f60a"
        ),
    },
    {
        "name": "Closing - Ticket Created",
        "category": "Closing",
        "content": (
            "Dear {customer_name} @ {company},\n\n"
            "We've created a support ticket for your issue. Our team will review and follow up shortly.\n\n"
            "In the meantime, if you have any additional information that might help us resolve this faster, "
            "please feel free to share it here.\n\n"
            "Thank you for your patience. We'll keep you updated on the progress!"
        ),
    },
]

if __name__ == "__main__":
    for m in macros:
        db_manager.create_macro(m["name"], m["content"], m["category"])
        print(f"  [+] {m['category']} / {m['name']}")
    
    print(f"\nDone! {len(macros)} closing macros created.")
    
    all_macros = db_manager.get_macros()
    print(f"\nAll macros in DB ({len(all_macros)}):")
    for m in all_macros:
        print(f"  [{m['category']}] {m['name']}")
