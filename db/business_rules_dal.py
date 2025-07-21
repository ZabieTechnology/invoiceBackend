import logging
from datetime import datetime

# Assuming you might want to add activity logging later
# from .activity_log_dal import add_activity

BUSINESS_RULES_COLLECTION = 'business_rules'
logging.basicConfig(level=logging.INFO)

def get_business_rules(db_conn, tenant_id="default_tenant"):
    """
    Fetches the business rules document for a specific tenant.
    """
    try:
        rules_doc = db_conn[BUSINESS_RULES_COLLECTION].find_one(
            {"_id": f"business_rules_{tenant_id}"}
        )
        return rules_doc.get("business_types", None) if rules_doc else None
    except Exception as e:
        logging.error(f"Error fetching business rules for tenant {tenant_id}: {e}")
        raise

def save_business_rules(db_conn, rules_data, user="System", tenant_id="default_tenant"):
    """
    Saves the business rules document for a specific tenant using upsert.
    """
    try:
        now = datetime.utcnow()
        result = db_conn[BUSINESS_RULES_COLLECTION].update_one(
            {"_id": f"business_rules_{tenant_id}"},
            {
                "$set": {
                    "business_types": rules_data,
                    "updated_date": now,
                    "updated_user": user
                }
            },
            upsert=True
        )
        logging.info(f"Business rules for tenant {tenant_id} saved by {user}.")
        # Example of activity logging you could add:
        # add_activity(
        #     action_type="UPDATE_BUSINESS_RULES",
        #     user=user,
        #     details="Updated global business rule settings.",
        #     document_id=f"business_rules_{tenant_id}",
        #     collection_name=BUSINESS_RULES_COLLECTION,
        #     tenant_id=tenant_id
        # )
        return result
    except Exception as e:
        logging.error(f"Error saving business rules for tenant {tenant_id}: {e}")
        raise

def get_default_business_types():
    """
    Generates a default list of business types and their rules.
    This is used to populate the database if it's empty.
    """
    def create_rules(pan_char):
        pan = f"10-character alphanumeric identifier.\nThe 4th character must be '{pan_char}' for this entity type.\nFirst 5 & last character are letters.\nCharacters 6 to 9 are numbers."
        gstin = "15-digit unique number.\nFirst 2 digits are the state code.\nNext 10 digits are the business's PAN.\nLast 3 digits are for entity number, a default 'Z', and a checksum."
        tan = "10-digit alphanumeric number.\nFormat: AAAA12345A.\nFirst 4 chars are letters.\nNext 5 chars are numbers.\nLast char is a letter."
        return pan, gstin, tan

    types = [
        ("Private Company", "A company with privately held shares.", "C"),
        ("Public Company", "A company whose shares are traded on a public stock exchange.", "C"),
        ("One Person Company (OPC)", "A company with only one member.", "C"),
        ("Foreign Company", "A company incorporated outside India with business operations in India.", "C"),
        ("Partnership Firm", "A business structure where two or more individuals manage a business.", "F"),
        ("Limited Liability Partnership (LLP)", "A partnership where some or all partners have limited liabilities.", "F"),
        ("Association of Persons", "A group of persons who come together for a common purpose.", "A"),
        ("Body of Individuals", "A group of individuals who come together for a common purpose.", "B"),
        ("Hindu Undivided Family (HUF)", "A family-based entity recognized under Hindu law.", "H"),
        ("Trusts", "For entities established under a trust deed.", "T"),
        ("Government", "For government bodies and agencies.", "G"),
        ("Sole proprietorships", "A business owned and run by one individual.", "P"),
    ]

    all_business_types = []
    for name, desc, char in types:
        pan_rules, gstin_rules, tan_rules = create_rules(char)
        all_business_types.append({
            "name": name,
            "description": desc,
            "pan_rules": pan_rules,
            "gstin_rules": gstin_rules,
            "tan_rules": tan_rules,
        })
    return all_business_types
