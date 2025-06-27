# db/credit_note_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import traceback

from .activity_log_dal import add_activity
from .inventory_dal import add_stock_transaction
from .invoice_settings_dal import get_invoice_settings

CREDIT_NOTE_COLLECTION = 'credit_notes'
INVOICE_SETTINGS_COLLECTION = 'invoice_settings'
logging.basicConfig(level=logging.INFO)

def _serialize_credit_note(note):
    """
    Helper function to convert ObjectId fields in a credit note document to strings.
    """
    if not note:
        return None
    if '_id' in note and isinstance(note.get('_id'), ObjectId):
        note['_id'] = str(note['_id'])
    # Add other conversions if needed, e.g., for customer or item IDs
    return note

def create_credit_note(db_conn, credit_note_data, user, tenant_id):
    """
    Creates a new credit note, generates a number, and updates stock for returns.
    """
    try:
        now = datetime.utcnow()
        settings_collection = db_conn[INVOICE_SETTINGS_COLLECTION]

        # Get settings to generate the next number.
        # This assumes credit note settings are stored within invoice_settings.
        settings = get_invoice_settings(db_conn, tenant_id)

        # Safely access nested keys for credit note numbering
        global_settings = settings.get('global', {})
        next_number = global_settings.get('nextCreditNoteNumber', 1)

        # Find the default theme for the prefix
        default_theme = next((theme for theme in settings.get('savedThemes', []) if theme.get('isDefault')), {})
        prefix = default_theme.get('creditNotePrefix', 'CRN-')

        credit_note_data['creditNoteNumber'] = f"{prefix}{next_number}"
        credit_note_data['created_date'] = now
        credit_note_data['updated_date'] = now
        credit_note_data['created_by'] = user
        credit_note_data['tenant_id'] = tenant_id
        credit_note_data.pop('_id', None)

        credit_note_collection = db_conn[CREDIT_NOTE_COLLECTION]
        result = credit_note_collection.insert_one(credit_note_data)
        inserted_id = result.inserted_id
        logging.info(f"Credit Note '{credit_note_data['creditNoteNumber']}' created with ID: {inserted_id}")

        # Atomically increment the next credit note number
        settings_collection.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {"global.nextCreditNoteNumber": 1}}
        )

        add_activity(
            action_type="CREATE_CREDIT_NOTE",
            user=user,
            details=f"Created Credit Note: {credit_note_data['creditNoteNumber']}",
            document_id=inserted_id,
            collection_name=CREDIT_NOTE_COLLECTION,
            tenant_id=tenant_id
        )

        # If goods are returned, update inventory stock
        if credit_note_data.get('reason') == 'Returned or Damaged Goods':
            for item in credit_note_data.get('lineItems', []):
                if item.get('itemId'):
                    add_stock_transaction(
                        db_conn=db_conn,
                        item_id=item['itemId'],
                        transaction_type='IN', # Stock comes back IN
                        quantity=item.get('quantity', 0),
                        notes=f"Return against Credit Note #{credit_note_data['creditNoteNumber']}",
                        user=user,
                        tenant_id=tenant_id
                    )

        return inserted_id
    except Exception as e:
        logging.error(f"Error creating credit note for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise

def get_credit_note_by_id(db_conn, note_id, tenant_id):
    try:
        note = db_conn[CREDIT_NOTE_COLLECTION].find_one({"_id": ObjectId(note_id), "tenant_id": tenant_id})
        return _serialize_credit_note(note)
    except Exception as e:
        logging.error(f"Error fetching credit note by ID {note_id}: {e}")
        raise

def get_all_credit_notes(db_conn, tenant_id):
    try:
        notes = list(db_conn[CREDIT_NOTE_COLLECTION].find({"tenant_id": tenant_id}).sort("issueDate", -1))
        return [_serialize_credit_note(note) for note in notes]
    except Exception as e:
        logging.error(f"Error fetching all credit notes for tenant {tenant_id}: {e}")
        raise
