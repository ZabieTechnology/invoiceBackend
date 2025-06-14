# invoiceBackend/utils/helpers.py
import uuid
from datetime import datetime

def generate_transaction_number(prefix="INV-TRAN"):
    date_str = datetime.utcnow().strftime("%Y%m%d")
    unique_id = str(uuid.uuid4().hex)[:6].upper()
    return f"{prefix}-{date_str}-{unique_id}"

# --- END OF utils/helpers.py ---