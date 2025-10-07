

# utils/metadata_extractor.py

import re
import io
from datetime import date
import mysql.connector
import pdfplumber
from config.db_config import db_config

# ----------------------------------------
# Helpers
# ----------------------------------------
DATE_RE = re.compile(
    r"(\d{1,2}\s*[.\-\/]\s*\d{1,2}\s*[.\-\/]\s*\d{2,4})"
    r"|(\d{1,2}\s*[-]\s*(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*[-]\s*\d{2,4})",
    re.I
)

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12
}

def _parse_date_flexible(raw: str):
    if not raw:
        return None
    s = re.sub(r"\s*([.\-\/])\s*", r"\1", raw.strip()).strip()
    s = re.sub(r"\s*([-])\s*", r"\1", s)
    m = DATE_RE.search(s)
    if not m:
        return None
    if m.group(1):
        parts = re.split(r"[.\-\/]", m.group(1))
        if len(parts) != 3:
            return None
        d, mth, y = map(int, parts)
        if y < 100:
            y += 2000 if y < 50 else 1900
        try:
            return date(y, mth, d)
        except ValueError:
            try:
                return date(y, d, mth)
            except ValueError:
                return None
    elif m.group(2):
        parts = re.split(r"\s*-\s*", m.group(2))
        if len(parts) != 3:
            return None
        d, mth, y = parts
        d, y = int(d), int(y)
        mth = MONTH_MAP.get(mth.lower())
        if not mth:
            return None
        if y < 100:
            y += 2000 if y < 50 else 1900
        try:
            return date(y, mth, d)
        except ValueError:
            return None
    return None

# ----------------------------------------
# MP Names Extractor
# ----------------------------------------
def extract_mp_names(all_text: str):
    lines = [ln.strip() for ln in all_text.splitlines() if ln.strip()]
    mp_names = []
    capture = False
    for ln in lines:
        if re.match(r'^\s*[#†*]*\d+\s*[.\-]?\s*', ln):
            capture = True
            cleaned = re.sub(r'^\s*[#†*]*\d+\s*[.\-]?\s*', '', ln).strip()
            cleaned = re.sub(r'^\s*[#†*.]+', '', cleaned).strip()
            if cleaned:
                mp_names.append(cleaned.rstrip(':').strip())
            continue
        if capture:
            if re.match(r'^(Will the Minister|ANSWERED|TO BE ANSWERED)', ln, re.I):
                break
            cleaned = re.sub(r'^\s*[#†*.]+', '', ln).strip()
            if cleaned:
                mp_names.append(cleaned.rstrip(':').strip())
    return mp_names

# ----------------------------------------
# Extract sub-questions (a), (b), ...
# ----------------------------------------
def extract_qa_pairs(all_text: str):
    qa_list = []
    start_match = re.search(
        r"Will the Minister of Youth Affairs and Sports be pleased to state", all_text, re.I
    )
    if not start_match:
        return qa_list
    text_after_start = all_text[start_match.end():]
    end_match = re.search(r"\bANSWER\b", text_after_start, re.I)
    text_block = text_after_start[:end_match.start()] if end_match else text_after_start
    matches = re.findall(r"\(([a-z])\)\s*(.*?)(?=\([a-z]\)|$)", text_block, re.I | re.S)
    for label, question in matches:
        question_clean = " ".join(question.split())
        qa_list.append({"sub_question_label": label.lower(), "question": question_clean})
    return qa_list

# ----------------------------------------
# Metadata extractor from blob
# ----------------------------------------
def extract_details_from_blob(blob_data: bytes):
    try:
        with pdfplumber.open(io.BytesIO(blob_data)) as pdf:
            all_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return {}, []

    details = {
        "question_number": None,
        "department": None,
        "mp_name": None,
        "answered_on": None,
        "subject": None,
        "house": None,
        "issuing_person": None,
        "place": None,
        "date": None
    }

    all_text = all_text.replace("†", "*")

    # House
    house_pat = re.compile(r"(?:LOK\s*SABHA|LOKSABHA|RAJYA\s*SABHA|RAJYASABHA)", re.I)
    for line in all_text.splitlines():
        m = house_pat.search(line)
        if m:
            house_name = m.group(0).upper()
            details["house"] = "Lok Sabha" if "LOK" in house_name else "Rajya Sabha"
            break

    # MP Names
    details["mp_name"] = ", ".join(extract_mp_names(all_text)) if all_text else None

    # Issuing Person
    pattern = re.compile(
        r"ANSWER\s+THE\s+MINISTER\s+OF\s+[A-Z &]+?\s*\n(.*?)(?:\n|$)", re.I
    )
    match = pattern.search(all_text)
    details["issuing_person"] = match.group(1).strip() if match else None

    # Question number
    qpat = re.compile(r"(?:STARRED|UNSTARRED)?\s*QUESTION\s*NO\.?\s*[#†*]*[:\-]?\s*(\d+)", re.I)
    m = qpat.search(all_text)
    details["question_number"] = m.group(1) if m else None

    # Subject & Answered On
    date_match = DATE_RE.search(all_text)
    details["answered_on"] = _parse_date_flexible(date_match.group(0)) if date_match else None
    details["subject"] = all_text[:500].replace("\n", " ").strip() if all_text else None

    # Extract QA pairs
    qa_pairs = extract_qa_pairs(all_text)

    return details, qa_pairs

# ----------------------------------------
# DB Save Function (metadata + QA)
# ----------------------------------------
def process_blobs_and_save_metadata():
    """Fetch blobs from DB, extract metadata & QA, and save to metadata + qa_pairs tables."""
    try:
        conn = mysql.connector.connect(**db_config, database="parliament_data")
        cursor = conn.cursor(buffered=True)  # buffered to avoid Unread result found

        cursor.execute("SELECT id, file_name, file_data FROM blob_data")
        files = cursor.fetchall()

        for file_id, file_name, file_data in files:
            print(f"📂 Processing {file_name} (id={file_id})...")
            details, qa_pairs = extract_details_from_blob(file_data)

            # Save metadata
            insert_meta = """
                INSERT INTO metadata 
                (file_id, question_number, department, mp_name, answered_on, subject, house, issuing_person, place, date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    question_number = VALUES(question_number),
                    department = VALUES(department),
                    mp_name = VALUES(mp_name),
                    answered_on = VALUES(answered_on),
                    subject = VALUES(subject),
                    house = VALUES(house),
                    issuing_person = VALUES(issuing_person),
                    place = VALUES(place),
                    date = VALUES(date)
            """
            cursor.execute(insert_meta, (
                file_id,
                details.get("question_number"),
                details.get("department"),
                details.get("mp_name"),
                details.get("answered_on"),
                details.get("subject"),
                details.get("house"),
                details.get("issuing_person"),
                details.get("place"),
                details.get("date")
            ))
            conn.commit()

            # Get metadata_id for qa_pairs
            cursor.execute("SELECT id FROM metadata WHERE file_id = %s", (file_id,))
            metadata_id = cursor.fetchone()[0]

            # Save QA pairs with answer=None
            for qa in qa_pairs:
                cursor.execute("""
                    INSERT INTO qa_pairs (metadata_id, sub_question_label, question, answer)
                    VALUES (%s, %s, %s, %s)
                """, (metadata_id, qa["sub_question_label"], qa["question"], None))
            conn.commit()
            print(f"✅ Metadata + {len(qa_pairs)} QA pairs saved for file_id={file_id}")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")

# ✅ Standalone testing
if __name__ == "__main__":
    process_blobs_and_save_metadata()
