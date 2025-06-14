# api/document_ai.py
from flask import Blueprint, request, jsonify, current_app
import logging
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import json
import re

from google.cloud import documentai_v1beta3 as documentai

document_ai_bp = Blueprint(
    'document_ai_bp',
    __name__,
    url_prefix='/api/document-ai'
)

logging.basicConfig(level=logging.INFO)
EXTRACTION_LOG_FOLDER_CONFIG_KEY = 'EXTRACTION_LOG_FOLDER'

def get_field_text(field_entity, document_text):
    if not field_entity: return None
    # Prefer normalized text if available and makes sense for the field type
    if field_entity.normalized_value and field_entity.normalized_value.text:
        # Check if normalized_value.text is not empty, otherwise fallback to mention_text
        normalized_text = field_entity.normalized_value.text.strip()
        if normalized_text:
            return normalized_text
    if field_entity.mention_text:
        return field_entity.mention_text.strip()
    return None

def get_currency_value(field_entity, document_text):
    if field_entity and field_entity.normalized_value and field_entity.normalized_value.money_value:
        money = field_entity.normalized_value.money_value
        return float(money.units) + (money.nanos / 1e9) if money.units is not None else None

    text_value = get_field_text(field_entity, document_text)
    if text_value:
        try:
            cleaned_value = re.sub(r'[₹$,A-Za-z]', '', text_value).replace(',', '').strip() # Remove common currency symbols and letters
            if not cleaned_value: return None # If only symbols were present
            return float(cleaned_value)
        except ValueError:
            logging.warning(f"Could not parse currency value from text: '{text_value}'")
            return None
    return None

def get_date_value(field_entity, document_text):
    if field_entity and field_entity.normalized_value and field_entity.normalized_value.date_value:
        gcp_date = field_entity.normalized_value.date_value
        if gcp_date.year and gcp_date.month and gcp_date.day and gcp_date.year != 0:
            return datetime(gcp_date.year, gcp_date.month, gcp_date.day).date().isoformat()

    text_value = get_field_text(field_entity, document_text)
    if text_value:
        formats_to_try = ['%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%b-%y', '%b %d, %Y', '%d %b %Y', '%m/%d/%Y']
        for fmt in formats_to_try:
            try:
                parsed_date = datetime.strptime(text_value, fmt)
                return parsed_date.date().isoformat()
            except ValueError:
                continue
        logging.warning(f"Could not parse date value with known formats: '{text_value}'")
        return text_value
    return None


def map_gcp_invoice_to_form(document):
    mapped_data = {}
    document_text = document.text

    initial_fields = {
        'billNo': None, 'billDate': None, 'supplier': None, 'supplierGst': None,
        'dueDate': None, 'totalAmount': None, 'subTotalFromItems': None,
        'taxAmount': None, 'cgstAmount': None, 'sgstAmount': None,
        'igstAmount': None, 'cessAmount': None, 'narration': None, 'currency': 'INR'
    }
    mapped_data = {**initial_fields, "lineItems": []}

    temp_cgst = 0.0
    temp_sgst = 0.0
    temp_igst = 0.0
    temp_cess = 0.0

    product_line_items_subtotal_sum = 0.0 # Sum of amounts from actual product/service lines

    logging.info("--- Mapping Google Document AI Entities (Indian Invoice Focus v2) ---")

    # Store entities by type for easier access
    entities_by_type = {}
    for entity in document.entities:
        entities_by_type.setdefault(entity.type_, []).append(entity)

    # General Invoice Information
    mapped_data['billNo'] = get_field_text(entities_by_type.get('invoice_id', [None])[0], document_text)
    mapped_data['billDate'] = get_date_value(entities_by_type.get('invoice_date', [None])[0], document_text)
    mapped_data['supplier'] = get_field_text(entities_by_type.get('supplier_name', [None])[0], document_text)
    mapped_data['supplierGst'] = get_field_text(entities_by_type.get('supplier_tax_id', [None])[0], document_text)
    mapped_data['dueDate'] = get_date_value(entities_by_type.get('due_date', [None])[0], document_text)
    currency_entity = entities_by_type.get('currency', [None])[0]
    if currency_entity and get_field_text(currency_entity, document_text):
        mapped_data['currency'] = get_field_text(currency_entity, document_text).upper()

    # Amounts - Grand Total and Net Amount (Subtotal before summary taxes)
    mapped_data['totalAmount'] = get_currency_value(entities_by_type.get('total_amount', [None])[0], document_text)
    mapped_data['subTotalFromItems'] = get_currency_value(entities_by_type.get('net_amount', [None])[0], document_text)

    logging.info(f"  Initial extracted totals: GrandTotal={mapped_data['totalAmount']}, Net(SubTotal)={mapped_data['subTotalFromItems']}")

    # Process Line Items and Summary Tax Lines
    # Google's Invoice Parser often lists summary taxes (CGST, SGST) as 'line_item' entities
    # after the actual product/service lines.
    if 'line_item' in entities_by_type:
        for entity in entities_by_type['line_item']:
            item_description_entity = next((p for p in entity.properties if p.type_ == 'line_item_description'), None)
            item_description = get_field_text(item_description_entity, document_text)

            item_amount_entity = next((p for p in entity.properties if p.type_ == 'line_item_amount'), None)
            item_amount = get_currency_value(item_amount_entity, document_text)

            logging.debug(f"  Processing line_item entity: Description='{item_description}', Amount='{item_amount}'")

            is_tax_component_line = False
            if item_description and item_amount is not None: # Amount must be present
                desc_lower = item_description.lower()
                if re.search(r'(cgst|central\s*(gst|tax))', desc_lower):
                    temp_cgst += item_amount
                    is_tax_component_line = True
                    logging.info(f"    -> Line item identified as CGST: {item_amount} (Desc: '{item_description}')")
                elif re.search(r'(sgst|state\s*(gst|tax))', desc_lower):
                    temp_sgst += item_amount
                    is_tax_component_line = True
                    logging.info(f"    -> Line item identified as SGST: {item_amount} (Desc: '{item_description}')")
                elif re.search(r'(igst|integrated\s*(gst|tax))', desc_lower):
                    temp_igst += item_amount
                    is_tax_component_line = True
                    logging.info(f"    -> Line item identified as IGST: {item_amount} (Desc: '{item_description}')")
                elif "cess" in desc_lower:
                    temp_cess += item_amount
                    is_tax_component_line = True
                    logging.info(f"    -> Line item identified as CESS: {item_amount} (Desc: '{item_description}')")

            if not is_tax_component_line: # It's a regular product/service line item
                line_item_obj = {'description': item_description, 'hsnCode': None, 'qty': None, 'price': None, 'subtotal': item_amount}
                for prop in entity.properties:
                    prop_type = prop.type_
                    if prop_type == 'line_item_quantity':
                        qty_text = get_field_text(prop, document_text)
                        try: line_item_obj['qty'] = float(qty_text.replace(',','')) if qty_text else None
                        except ValueError: line_item_obj['qty'] = None
                    elif prop_type == 'line_item_unit_price':
                        line_item_obj['price'] = get_currency_value(prop, document_text)
                    elif prop_type == 'line_item_product_code':
                        line_item_obj['hsnCode'] = get_field_text(prop, document_text)

                if any(val is not None for val in line_item_obj.values()): # Add if it has some data
                    mapped_data['lineItems'].append(line_item_obj)
                    if line_item_obj.get('subtotal') is not None:
                         product_line_items_subtotal_sum += line_item_obj['subtotal']

    # Consolidate individual tax amounts
    if temp_cgst > 0: mapped_data['cgstAmount'] = temp_cgst
    if temp_sgst > 0: mapped_data['sgstAmount'] = temp_sgst
    if temp_igst > 0: mapped_data['igstAmount'] = temp_igst
    if temp_cess > 0: mapped_data['cessAmount'] = temp_cess

    # Calculate total taxAmount from components
    sum_of_components = temp_cgst + temp_sgst + temp_igst + temp_cess
    if sum_of_components > 0:
        mapped_data['taxAmount'] = sum_of_components
        logging.info(f"Total taxAmount set from sum of components: {sum_of_components}")
    elif mapped_data.get('taxAmount') is None: # If not set by 'total_tax_amount' entity and components are 0
        # If totalAmount and subTotalFromItems (net_amount) are present, derive taxAmount
        if mapped_data.get('totalAmount') is not None and mapped_data.get('subTotalFromItems') is not None:
            derived_tax = mapped_data['totalAmount'] - mapped_data['subTotalFromItems']
            if derived_tax >= 0: # Tax cannot be negative
                mapped_data['taxAmount'] = derived_tax
                logging.info(f"Derived taxAmount from totalAmount - subTotalFromItems: {derived_tax}")
            else:
                mapped_data['taxAmount'] = 0.0
        else:
            mapped_data['taxAmount'] = 0.0
        logging.info(f"No tax components found. taxAmount is: {mapped_data['taxAmount']}")

    # If subTotalFromItems (net_amount from GCP) was not found or is zero,
    # and we have line items, use their sum as subTotalFromItems.
    # This also helps if GCP's 'net_amount' is actually the sum of line items *after* line item taxes.
    if mapped_data.get('subTotalFromItems') is None or mapped_data.get('subTotalFromItems') == 0.0:
        if product_line_items_subtotal_sum > 0:
            mapped_data['subTotalFromItems'] = product_line_items_subtotal_sum
            logging.info(f"Using sum of product/service line items for subTotalFromItems: {product_line_items_subtotal_sum}")
        elif mapped_data.get('totalAmount') is not None and mapped_data.get('taxAmount') is not None:
            # Recalculate if total and tax are known but subtotal was 0
            derived_subtotal = mapped_data['totalAmount'] - mapped_data['taxAmount']
            if derived_subtotal >=0: mapped_data['subTotalFromItems'] = derived_subtotal

    # Ensure numeric fields are numbers or None
    for key in ['totalAmount', 'subTotalFromItems', 'taxAmount', 'cgstAmount', 'sgstAmount', 'igstAmount', 'cessAmount']:
        if mapped_data.get(key) is not None:
            try: mapped_data[key] = float(mapped_data[key])
            except (ValueError, TypeError):
                 logging.warning(f"Final conversion: Could not convert mapped field {key} to float: {mapped_data[key]}")
                 mapped_data[key] = None

    logging.info(f"Final Mapped GCP Document AI data for frontend: {json.dumps(mapped_data, default=str)}")
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
            project_id = current_app.config.get('GCP_PROJECT_ID')
            location = current_app.config.get('GCP_LOCATION')
            processor_id = current_app.config.get('GCP_PROCESSOR_ID')
            extraction_log_folder = current_app.config.get(EXTRACTION_LOG_FOLDER_CONFIG_KEY)

            if not all([project_id, location, processor_id]):
                logging.error("Google Cloud Document AI project, location, or processor ID is not configured.")
                return jsonify({"message": "Google Cloud Document AI service not configured on server."}), 500

            opts = {}
            if location and location not in ['us', 'eu']:
                 opts = {"api_endpoint": f"{location}-documentai.googleapis.com"}

            client = documentai.DocumentProcessorServiceClient(client_options=opts if opts else None)

            mime_type = file.content_type
            file_content = file.read()

            name = client.processor_path(project_id, location, processor_id)

            raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
            request_doc_ai = documentai.ProcessRequest(name=name, raw_document=raw_document)

            result = client.process_document(request=request_doc_ai)
            document = result.document

            raw_extracted_text_content = document.text if document else None

            if extraction_log_folder and document:
                try:
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
                    log_filename = f"gcp_extraction_raw_{timestamp}.json"
                    log_file_path = os.path.join(extraction_log_folder, log_filename)

                    from google.protobuf.json_format import MessageToJson
                    json_output = MessageToJson(document)

                    with open(log_file_path, 'w') as f:
                        f.write(json_output)
                    logging.info(f"Raw GCP Document AI extraction result saved to: {log_file_path}")
                except Exception as log_e:
                    logging.error(f"Error saving raw GCP extraction log: {log_e}")

            # This object structure will be passed to the frontend.
            # Frontend's AddExpensePage.js handleFileChange will then populate its formData state
            # from this 'extractedData' object.
            output_for_frontend = {
                 "fieldMappings": [], # For the new table display
                 "lineItems": [],
                 "rawFields": {} # A direct mapping of what map_gcp_invoice_to_form produces
            }

            if document:
                mapped_form_fields = map_gcp_invoice_to_form(document)
                output_for_frontend["rawFields"] = mapped_form_fields

                for label, value in mapped_form_fields.items():
                    if label != "lineItems":
                        output_for_frontend["fieldMappings"].append({"label": label, "value": value if value is not None else ''})

                if mapped_form_fields.get("lineItems"):
                    output_for_frontend["lineItems"] = mapped_form_fields["lineItems"]

            else:
                logging.info("No document processed by Google Document AI.")
                return jsonify({"message": "No invoice data could be extracted by Google AI."}), 400

            return jsonify({
                "message": "Invoice data extracted successfully via Google AI",
                "extractedData": output_for_frontend["rawFields"],
                "extractedTableData": output_for_frontend["fieldMappings"],
                "extractedLineItems": output_for_frontend["lineItems"],
                "rawText": raw_extracted_text_content
            }), 200

        except Exception as e:
            logging.exception(f"Error during Google Document AI processing: {e}")
            return jsonify({"message": f"Error processing invoice with Google AI: {str(e)}"}), 500

    return jsonify({"message": "File processing error"}), 400
