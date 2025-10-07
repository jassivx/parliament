# utils/metadata_extractor.py
import re
import io
from datetime import date
import mysql.connector
from config.db_config import db_config
from PyPDF2 import PdfReader# import re
# from PyPDF2 import PdfReader
#
# def extract_issuing_person_from_pdf(pdf_path: str):
#     # Read PDF
#     reader = PdfReader(pdf_path)
#     text = "\n".join(page.extract_text() or "" for page in reader.pages)
#
#     # Normalize spaces
#     text = re.sub(r"[ \t]+", " ", text)
#
#     # Regex: find "ANSWER THE MINISTER ..." and capture what follows
#     pattern = re.compile(
#         r"ANSWER\s+THE\s+MINISTER\s+OF\s+[A-Z &]+?\s*\n(.*?)(?:\n|$)",
#         re.I
#     )
#
#     match = pattern.search(text)
#     if match:
#         issuing_person = match.group(1).strip()
#         return issuing_person
#     else:
#         return None
#
#
# # 🔹 Demo
# if __name__ == "__main__":
#     pdf_file = r"C:/Users/HP/Documents/Scanned Documents/doc/ru479.pdf"
#     result = extract_issuing_person_from_pdf(pdf_file)
#     if result:
#         print("📌 Issuing Person:", result)
#     else:
#         print("❌ Issuing Person not found")



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
    r"(\d{1,2}\s*[.\-\/]\s*\d{1,2}\s*[.\-\/]\s*\d{2,4})"  # Numeric: 13/02/2025, 13-02-2025, 13.02.2025
    r"|(\d{1,2}\s*[-]\s*(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*[-]\s*\d{2,4})",  # Textual: 13-Feb-2025
    re.I
)

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12
}

def _parse_date_flexible(raw: str):
    """Normalize a date string like '13/02/2025', '13-02-2025', or '13-Feb-2025' to a Python date."""
    if not raw:
        return None
    s = re.sub(r"\s*([.\-\/])\s*", r"\1", raw.strip()).strip()
    s = re.sub(r"\s*([-])\s*", r"\1", s)  # For textual dates with hyphens
    m = DATE_RE.search(s)
    if not m:
        return None

    if m.group(1):  # Numeric format
        parts = re.split(r"[.\-\/]", m.group(1))
        if len(parts) != 3:
            return None
        d, mth, y = parts
        d, mth, y = int(d), int(mth), int(y)
        if y < 100:
            y += 2000 if y < 50 else 1900
        try:
            return date(y, mth, d)  # d/m/y
        except ValueError:
            try:
                return date(y, d, mth)  # m/d/y
            except ValueError:
                return None
    elif m.group(2):  # Textual format
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
# 👤 MP Names Extractor
# ----------------------------------------
def extract_mp_names(all_text: str):
    """Extract MP names from PDF text block."""
    lines = [ln.strip() for ln in all_text.splitlines() if ln.strip()]
    mp_names = []
    capture = False

    for ln in lines:
        # Detect start of Q.No. block (allow #, †, or * before number, and optional . or -)
        if re.match(r'^\s*[#†*]*\d+\s*[.\-]?\s*', ln):
            capture = True
            # Remove Q.No. part and any leading #, #., †, or *
            cleaned = re.sub(r'^\s*[#†*]*\d+\s*[.\-]?\s*', '', ln).strip()
            # Remove any remaining leading special characters
            cleaned = re.sub(r'^\s*[#†*.]+', '', cleaned).strip()
            if cleaned:
                mp_names.append(cleaned.rstrip(':').strip())
            continue

        if capture:
            # Stop when minister line starts
            if re.match(r'^(Will the Minister|ANSWERED|TO BE ANSWERED)', ln, re.I):
                break
            # Clean any leading special characters from subsequent lines
            cleaned = re.sub(r'^\s*[#†*.]+', '', ln).strip()
            if cleaned:
                mp_names.append(cleaned.rstrip(':').strip())

    return mp_names

# ----------------------------------------
# 📄 Metadata Extractor
# ----------------------------------------
def extract_details_from_blob(blob_data: bytes):
    """Extract structured details from a PDF blob."""
    try:
        with pdfplumber.open(io.BytesIO(blob_data)) as pdf:
            all_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return {
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
    raw_lines = all_text.split("\n")
    lines = [ln.strip() for ln in raw_lines if ln and ln.strip()]

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

    # House
    house_pat = re.compile(r"(?:LOK\s*SABHA|LOKSABHA|RAJYA\s*SABHA|RAJYASABHA)", re.I)
    for line in lines:
        m = house_pat.search(line)
        if m:
            house_name = m.group(0).upper()
            if "LOK" in house_name:
                details["house"] = "Lok Sabha"
            elif "RAJYA" in house_name:
                details["house"] = "Rajya Sabha"
            break

    # Department
    for i, line in enumerate(lines):
        if details["house"] and re.search(r"(?:LOK\s*SABHA|LOKSABHA|RAJYA\s*SABHA|RAJYASABHA)", line, re.I):
            dept_lines = []
            for j in range(i - 1, -1, -1):
                if lines[j].strip() == "" or "GOVERNMENT OF INDIA" in lines[j].upper():
                    break
                dept_lines.insert(0, lines[j])
            details["department"] = " ".join(dept_lines).strip()
            break

    # Answered On + Subject
    answered_found = False
    for i, line in enumerate(lines):
        if re.search(r"ANSWE(?:R|RE)D\s+ON", line, re.I):
            look, nxt = line, (lines[i+1] if i+1 < len(lines) else "")
            m = DATE_RE.search(look) or DATE_RE.search(nxt) or DATE_RE.search(look + " " + nxt)
            details["answered_on"] = _parse_date_flexible(m.group(0)) if m else None

            k = i + 1
            while k < len(lines):
                if re.search(r"ANSWE(?:R|RE)D\s+ON", lines[k], re.I): k += 1; continue
                if DATE_RE.search(lines[k]) or re.fullmatch(r"[-–—:]+", lines[k]): k += 1; continue
                if lines[k].strip():
                    raw_subject = lines[k].strip()
                    details["subject"] = re.sub(r'[\'"\u2018\u2019\u201C\u201D]', '', raw_subject)[:500]
                    print(f"Raw subject: {raw_subject}")
                    print(f"Cleaned subject: {details['subject']}")
                    break
                k += 1
            answered_found = True
            break

    if not answered_found and not details["subject"]:
        for i, line in enumerate(lines):
            if re.search(r"(?:STARRED|UNSTARRED)?\s*QUESTION\s*NO\.?", line, re.I):
                k = i + 1
                while k < len(lines):
                    if re.search(r"ANSWE(?:R|RE)D\s+ON", lines[k], re.I):
                        kk = k + 1
                        while kk < len(lines) and (DATE_RE.search(lines[kk]) or re.search(r"ANSWE(?:R|RE)D\s+ON", lines[kk], re.I) or re.fullmatch(r"[-–—:]+", lines[kk])):
                            kk += 1
                        if kk < len(lines):
                            raw_subject = lines[kk].strip()
                            details["subject"] = re.sub(r'[\'"\u2018\u2019\u201C\u201D]', '', raw_subject)[:500]
                            print(f"Raw subject (fallback): {raw_subject}")
                            print(f"Cleaned subject (fallback): {details['subject']}")
                        break
                    if DATE_RE.search(lines[k]) or re.fullmatch(r"[-–—:]+", lines[k]) or not lines[k].strip():
                        k += 1; continue
                    raw_subject = lines[k].strip()
                    details["subject"] = re.sub(r'[\'"\u2018\u2019\u201C\u201D]', '', raw_subject)[:500]
                    print(f"Raw subject (fallback): {raw_subject}")
                    print(f"Cleaned subject (fallback): {details['subject']}")
                    break
                break

    # Question Number
    qpat = re.compile(r"(?:STARRED|UNSTARRED)?\s*QUESTION\s*NO\.?\s*[#†*]*[:\-]?\s*(\d+)", re.I)
    for line in lines:
        m = qpat.search(line)
        if m:
            details["question_number"] = m.group(1); break
    if not details["question_number"]:
        m = re.search(r"[#†*]*\s*(\d{1,4})\s*[:.\-]?\s*(?:(?:Shri|Smt\.?|Dr\.?|Prof\.?|Kumari|Km\.?|Ms\.?|Miss)\b)?", all_text, re.I)
        if m: details["question_number"] = m.group(1)

    # MP Names
    mp_names = extract_mp_names(all_text)
    details["mp_name"] = ", ".join(mp_names) if mp_names else None

    # Issuing Person
    normalized_text = re.sub(r"[ \t]+", " ", all_text)
    pattern = re.compile(
        r"ANSWER\s+THE\s+MINISTER\s+OF\s+[A-Z &]+?\s*\n(.*?)(?:\n|$)",
        re.I
    )
    match = pattern.search(normalized_text)
    if match:
        raw_issuing_person = match.group(1).strip()
        details["issuing_person"] = re.sub(r'[\(\)\{\}\[\]]', '', raw_issuing_person).strip()
        print(f"Raw issuing_person: {raw_issuing_person}")
        print(f"Cleaned issuing_person: {details['issuing_person']}")
    else:
        details["issuing_person"] = None

    return details

# ----------------------------------------
# 💾 DB Save Function
# ----------------------------------------
def process_blobs_and_save_metadata():
    """Fetch blobs from DB, extract details, and save/update metadata table."""
    try:
        conn = mysql.connector.connect(**db_config, database="parliament_data")
        cursor = conn.cursor()

        cursor.execute("SELECT id, file_name, file_data FROM blob_data")
        files = cursor.fetchall()

        for file_id, file_name, file_data in files:
            print(f"📂 Processing {file_name} (id={file_id})...")
            details = extract_details_from_blob(file_data)

            insert_query = """
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

            cursor.execute(insert_query, (
                file_id,
                details["question_number"],
                details["department"],
                details["mp_name"],
                details["answered_on"],
                details["subject"],
                details["house"],
                details["issuing_person"],
                details["place"],
                details["date"]
            ))

            conn.commit()
            print(f"✅ Metadata saved/updated for file_id={file_id}")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")

# ✅ Standalone testing
if __name__ == "__main__":
    process_blobs_and_save_metadata()










