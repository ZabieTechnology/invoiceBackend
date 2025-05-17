# api/document_ai.py
from flask import Blueprint, request, jsonify, current_app
import logging
import os
from werkzeug.utils import secure_filename
from datetime import datetime # Ensure datetime is imported

# Azure Document AI SDK
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient, DocumentField # Import DocumentField for type checking

document_ai_bp = Blueprint(
    'document_ai_bp',
    __name__,
    url_prefix='/api/document-ai'
)

logging.basicConfig(level=logging.INFO)

def get_field_value(field, field_type='string'):
    """ Safely gets the value from a DocumentField object. """
    if field:
        if field_type == 'currency' and field.value and hasattr(field.value, 'amount'):
            # For CurrencyValue, return the amount. You might also want symbol or code.
            return field.value.amount
        elif field_type == 'date' and field.value:
            return field.value.isoformat() # Convert date to ISO string
        elif field.value is not None: # For other types or if value is a primitive
            return field.value
    return None

def map_azure_fields_to_form(doc_fields):
    """
    Maps extracted fields from Azure Document AI prebuilt-invoice model
    to the field names expected by your frontend form.
    Handles CurrencyValue and DateValue objects.
    """
    mapped_data = {}
    
    # General document fields
    mapped_data['billNo'] = get_field_value(doc_fields.get('InvoiceId'))
    mapped_data['billDate'] = get_field_value(doc_fields.get('InvoiceDate'), field_type='date')
    mapped_data['supplier'] = get_field_value(doc_fields.get('VendorName'))
    mapped_data['supplierGst'] = get_field_value(doc_fields.get('VendorTaxId'))
    mapped_data['dueDate'] = get_field_value(doc_fields.get('DueDate'), field_type='date')
    
    # Amounts - Extract the 'amount' from CurrencyValue
    mapped_data['totalAmount'] = get_field_value(doc_fields.get('InvoiceTotal'), field_type='currency')
    mapped_data['subTotalFromItems'] = get_field_value(doc_fields.get('SubTotal'), field_type='currency')
    mapped_data['gstVatAmount'] = get_field_value(doc_fields.get('TotalTax'), field_type='currency')
    # You might need to calculate NetAmount or other fields based on these
    
    # Line Items
    line_items = []
    items_field = doc_fields.get('Items')
    if items_field and items_field.value: # Check if 'Items' field exists and has a value
        for item in items_field.value: # Iterate over the list of line items
            if item.value_type == "object" and item.value: # Each item is an object (DocumentField of type 'object')
                item_fields = item.value # Access the dictionary of fields within the line item
                line_item_data = {
                    'description': get_field_value(item_fields.get('Description')),
                    'qty': get_field_value(item_fields.get('Quantity')),
                    'price': get_field_value(item_fields.get('UnitPrice'), field_type='currency'),
                    'subtotal': get_field_value(item_fields.get('Amount'), field_type='currency'),
                    # Add other line item fields as needed
                    # 'productCode': get_field_value(item_fields.get('ProductCode')),
                    # 'tax': get_field_value(item_fields.get('Tax'), field_type='currency'),
                }
                line_items.append(line_item_data)
    mapped_data['lineItems'] = line_items

    logging.info(f"Mapped Azure data: {mapped_data}")
    return mapped_data


@document_ai_bp.route('/extract-invoice', methods=['POST'])
def extract_invoice_data():
    if 'invoice' not in request.files:
        return jsonify({"message": "No invoice file provided"}), 400

    file = request.files['invoice']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    if file:
        try:
            endpoint = current_app.config.get('AZURE_FORM_RECOGNIZER_ENDPOINT')
            key = current_app.config.get('AZURE_FORM_RECOGNIZER_KEY')

            if not endpoint or not key:
                logging.error("Azure Form Recognizer endpoint or key is not configured.")
                return jsonify({"message": "Azure Document AI service not configured on server."}), 500

            document_analysis_client = DocumentAnalysisClient(
                endpoint=endpoint, credential=AzureKeyCredential(key)
            )

            file_content = file.read()
            
            poller = document_analysis_client.begin_analyze_document(
                "prebuilt-invoice", document=file_content
            )
            result = poller.result()

            extracted_data = {}
            if result.documents and len(result.documents) > 0:
                document = result.documents[0]
                logging.info(f"Confidence for document: {document.confidence}")
                extracted_data = map_azure_fields_to_form(document.fields)
            else:
                logging.info("No documents found in the analysis result.")
                return jsonify({"message": "No invoice data could be extracted."}), 400

            return jsonify({"message": "Invoice data extracted successfully", "extractedData": extracted_data}), 200

        except Exception as e:
            logging.exception(f"Error during Azure Document AI processing: {e}") # Use .exception to log full traceback
            return jsonify({"message": f"Error processing invoice with Azure AI: {str(e)}"}), 500
    
    return jsonify({"message": "File processing error"}), 400
