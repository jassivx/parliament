# # utils/metadata_extractor.py
#
# import re
# import io
# from datetime import date
# import mysql.connector
# import pdfplumber
# from config.db_config import db_config
#
# # ----------------------------------------
# # Helpers
# # ----------------------------------------
# DATE_RE = re.compile(
#     r"(\d{1,2}\s*[.\-\/]\s*\d{1,2}\s*[.\-\/]\s*\d{2,4})"
#     r"|(\d{1,2}\s*[-]\s*(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*[-]\s*\d{2,4})",
#     re.I
# )
#
# MONTH_MAP = {
#     "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
#     "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
#     "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
#     "nov": 11, "november": 11, "dec": 12, "december": 12
# }
#
# def _parse_date_flexible(raw: str):
#     if not raw:
#         return None
#     s = re.sub(r"\s*([.\-\/])\s*", r"\1", raw.strip()).strip()
#     s = re.sub(r"\s*([-])\s*", r"\1", s)
#     m = DATE_RE.search(s)
#     if not m:
#         return None
#     if m.group(1):
#         parts = re.split(r"[.\-\/]", m.group(1))
#         if len(parts) != 3:
#             return None
#         d, mth, y = map(int, parts)
#         if y < 100:
#             y += 2000 if y < 50 else 1900
#         try:
#             return date(y, mth, d)
#         except ValueError:
#             try:
#                 return date(y, d, mth)
#             except ValueError:
#                 return None
#     elif m.group(2):
#         parts = re.split(r"\s*-\s*", m.group(2))
#         if len(parts) != 3:
#             return None
#         d, mth, y = parts
#         d, y = int(d), int(y)
#         mth = MONTH_MAP.get(mth.lower())
#         if not mth:
#             return None
#         if y < 100:
#             y += 2000 if y < 50 else 1900
#         try:
#             return date(y, mth, d)
#         except ValueError:
#             return None
#     return None
#
# # ----------------------------------------
# # MP Names Extractor
# # ----------------------------------------
# def extract_mp_names(all_text: str):
#     lines = [ln.strip() for ln in all_text.splitlines() if ln.strip()]
#     mp_names = []
#     capture = False
#     for ln in lines:
#         if re.match(r'^\s*[#†*]*\d+\s*[.\-]?\s*', ln):
#             capture = True
#             cleaned = re.sub(r'^\s*[#†*]*\d+\s*[.\-]?\s*', '', ln).strip()
#             cleaned = re.sub(r'^\s*[#†*.]+', '', cleaned).strip()
#             if cleaned:
#                 mp_names.append(cleaned.rstrip(':').strip())
#             continue
#         if capture:
#             if re.match(r'^(Will the Minister|ANSWERED|TO BE ANSWERED)', ln, re.I):
#                 break
#             cleaned = re.sub(r'^\s*[#†*.]+', '', ln).strip()
#             if cleaned:
#                 mp_names.append(cleaned.rstrip(':').strip())
#     return mp_names
#
# # ----------------------------------------
# # Extract sub-questions (a), (b), ...
# # ----------------------------------------
# # ----------------------------------------
# # Extract sub-questions (a), (b), ...
# # ----------------------------------------
# def extract_qa_pairs(all_text: str):
#     """
#     Extracts (a), (b), ... type questions from the text
#     specifically after the phrase:
#     'Will the Minister of YOUTH AFFAIRS AND SPORTS be pleased to state'
#     followed optionally by ':', ':-', ':—', '—', or similar punctuation.
#     """
#     qa_list = []
#
#     # Match the starting phrase (case-insensitive) and ignore any punctuation that follows
#     start_match = re.search(
#         r"Will\s+the\s+Minister\s+of\s+YOUTH\s+AFFAIRS\s+AND\s+SPORTS\s+be\s+pleased\s+to\s+state\s*[:\-–—]*",
#         all_text,
#         re.IGNORECASE
#     )
#     if not start_match:
#         return qa_list
#
#     # Text after the matched phrase
#     text_after_start = all_text[start_match.end():]
#
#     # Stop before "ANSWER" if it exists
#     end_match = re.search(r"\bANSWER\b", text_after_start, re.IGNORECASE)
#     text_block = text_after_start[:end_match.start()] if end_match else text_after_start
#
#     # Find sub-question patterns like (a), (b), etc.
#     # The `?=` lookahead ensures we capture until the next label or end of block
#     matches = re.findall(
#         r"\(([a-z])\)\s*(.*?)(?=\([a-z]\)|$)",
#         text_block,
#         re.IGNORECASE | re.DOTALL
#     )
#
#     # Clean and store
#     for label, question in matches:
#         question_clean = " ".join(question.split())
#         qa_list.append({
#             "sub_question_label": label.lower(),
#             "question": question_clean
#         })
#
#     return qa_list
#
#
# # ----------------------------------------
# # Metadata extractor from blob
# # ----------------------------------------
# def extract_details_from_blob(blob_data: bytes):
#     """Extract structured details from PDF blob with clean department, subject, and issuing_person."""
#     try:
#         with pdfplumber.open(io.BytesIO(blob_data)) as pdf:
#             all_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
#     except Exception as e:
#         print(f"Error reading PDF: {e}")
#         return {}, []
#
#     all_text = all_text.replace("†", "*")
#     lines = [ln.strip() for ln in all_text.splitlines() if ln.strip()]
#
#     details = {
#         "question_number": None,
#         "department": None,
#         "mp_name": None,
#         "answered_on": None,
#         "subject": None,
#         "house": None,
#         "issuing_person": None,
#         "place": None,
#         "date": None
#     }
#
#     # House
#     house_pat = re.compile(r"(?:LOK\s*SABHA|LOKSABHA|RAJYA\s*SABHA|RAJYASABHA)", re.I)
#     for line in lines:
#         m = house_pat.search(line)
#         if m:
#             house_name = m.group(0).upper()
#             details["house"] = "Lok Sabha" if "LOK" in house_name else "Rajya Sabha"
#             break
#
#     # Department (lines above House, remove "Government of India")
#     if details["house"]:
#         house_idx = next(i for i, l in enumerate(lines) if house_pat.search(l))
#         dept_lines = []
#         for j in range(house_idx - 1, -1, -1):
#             if lines[j].strip() == "" or "GOVERNMENT OF INDIA" in lines[j].upper():
#                 break
#             dept_lines.insert(0, lines[j])
#         details["department"] = " ".join(dept_lines).replace("GOVERNMENT OF INDIA", "").strip()
#
#     # Question Number
#     qpat = re.compile(r"(?:STARRED|UNSTARRED)?\s*QUESTION\s*NO\.?\s*[#†*]*[:\-]?\s*(\d+)", re.I)
#     for line in lines:
#         m = qpat.search(line)
#         if m:
#             details["question_number"] = m.group(1)
#             break
#     if not details["question_number"]:
#         m = re.search(r"[#†*]*\s*(\d{1,4})\s*[:.\-]?\s*(?:Shri|Smt\.?|Dr\.?|Prof\.?|Kumari|Km\.?|Ms\.?|Miss)?", all_text, re.I)
#         if m:
#             details["question_number"] = m.group(1)
#
#     # MP Names
#     details["mp_name"] = ", ".join(extract_mp_names(all_text)) if all_text else None
#
#     # Answered On
#     date_match = DATE_RE.search(all_text)
#     details["answered_on"] = _parse_date_flexible(date_match.group(0)) if date_match else None
#
#     # Subject (text after "TO BE ANSWERED ON <date>")
#     answered_on_match = re.search(r"TO BE ANSWERED ON\s*\d{1,2}[.\-\/]\d{1,2}[.\-\/]\d{2,4}", all_text, re.I)
#     if answered_on_match:
#         idx = answered_on_match.end()
#         remaining = all_text[idx:].strip()
#         remaining = re.sub(r"^\s*\d+\.\s*", "", remaining)
#         subject_line = remaining.split("\n")[0].strip()
#         details["subject"] = re.sub(r'[\[\]\*]', '', subject_line)
#
#     # Issuing Person (remove brackets)
#     pattern = re.compile(r"ANSWER\s+THE\s+MINISTER\s+OF\s+[A-Z &]+?\s*\n(.*?)(?:\n|$)", re.I)
#     match = pattern.search(all_text)
#     if match:
#         details["issuing_person"] = re.sub(r'[\[\]]', '', match.group(1)).strip()
#
#     # Extract QA pairs
#     qa_pairs = extract_qa_pairs(all_text)
#
#     return details, qa_pairs
#
# # ----------------------------------------
# # DB Save Function
# # ----------------------------------------
# def process_blobs_and_save_metadata():
#     """Fetch blobs from DB, extract metadata & QA, and save to metadata + qa_pairs tables."""
#     try:
#         conn = mysql.connector.connect(**db_config, database="parliament_data")
#         cursor = conn.cursor(buffered=True)
#
#         cursor.execute("SELECT id, file_name, file_data FROM blob_data")
#         files = cursor.fetchall()
#
#         for file_id, file_name, file_data in files:
#             print(f"📂 Processing {file_name} (id={file_id})...")
#             details, qa_pairs = extract_details_from_blob(file_data)
#
#             # Save metadata
#             insert_meta = """
#                 INSERT INTO metadata
#                 (file_id, question_number, department, mp_name, answered_on, subject, house, issuing_person, place, date)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#                 ON DUPLICATE KEY UPDATE
#                     question_number = VALUES(question_number),
#                     department = VALUES(department),
#                     mp_name = VALUES(mp_name),
#                     answered_on = VALUES(answered_on),
#                     subject = VALUES(subject),
#                     house = VALUES(house),
#                     issuing_person = VALUES(issuing_person),
#                     place = VALUES(place),
#                     date = VALUES(date)
#             """
#             cursor.execute(insert_meta, (
#                 file_id,
#                 details.get("question_number"),
#                 details.get("department"),
#                 details.get("mp_name"),
#                 details.get("answered_on"),
#                 details.get("subject"),
#                 details.get("house"),
#                 details.get("issuing_person"),
#                 details.get("place"),
#                 details.get("date")
#             ))
#             conn.commit()
#
#             # Get metadata_id for qa_pairs
#             cursor.execute("SELECT id FROM metadata WHERE file_id = %s", (file_id,))
#             metadata_id = cursor.fetchone()[0]
#
#             # Save QA pairs with answer=None
#             for qa in qa_pairs:
#                 cursor.execute("""
#                     INSERT INTO qa_pairs (metadata_id, sub_question_label, question, answer)
#                     VALUES (%s, %s, %s, %s)
#                 """, (metadata_id, qa["sub_question_label"], qa["question"], None))
#             conn.commit()
#             print(f"✅ Metadata + {len(qa_pairs)} QA pairs saved for file_id={file_id}")
#
#         cursor.close()
#         conn.close()
#
#     except mysql.connector.Error as err:
#         print(f"❌ MySQL error: {err}")
#
# # ✅ Standalone testing
# if __name__ == "__main__":
#     process_blobs_and_save_metadata()


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
    """
    Extracts (a), (b), ... type questions from the text
    specifically after the phrase:
    'Will the Minister of YOUTH AFFAIRS AND SPORTS be pleased to state'
    followed optionally by ':', ':-', ':—', '—', or similar punctuation.
    """
    qa_list = []

    start_match = re.search(
        r"Will\s+the\s+Minister\s+of\s+YOUTH\s+AFFAIRS\s+AND\s+SPORTS\s+be\s+pleased\s+to\s+state\s*[:\-–—]*",
        all_text,
        re.IGNORECASE
    )
    if not start_match:
        return qa_list

    text_after_start = all_text[start_match.end():]

    end_match = re.search(r"\bANSWER\b", text_after_start, re.IGNORECASE)
    text_block = text_after_start[:end_match.start()] if end_match else text_after_start

    matches = re.findall(
        r"\(([a-z])\)\s*(.*?)(?=\([a-z]\)|$)",
        text_block,
        re.IGNORECASE | re.DOTALL
    )

    for label, question in matches:
        question_clean = " ".join(question.split())
        qa_list.append({
            "sub_question_label": label.lower(),
            "question": question_clean
        })

    return qa_list


# ----------------------------------------
# Extract answers (a), (b), ...
# ----------------------------------------
def extract_answers(all_text: str):
    """
    Extracts answers corresponding to sub-questions (a), (b), (c), etc.
    from the 'ANSWER' section of the Parliament question text.
    Returns a dictionary like {'a': '...', 'b': '...', ...}.
    """
    answers_dict = {}

    ans_start = re.search(r"\bANSWER\b\s*[:\-–—]*", all_text, re.IGNORECASE)
    if not ans_start:
        return answers_dict

    ans_block = all_text[ans_start.end():]

    matches = re.findall(
        r"\(([a-z])\)\s*(.*?)(?=\([a-z]\)|$)",
        ans_block,
        re.IGNORECASE | re.DOTALL
    )

    for label, answer_text in matches:
        clean_text = " ".join(answer_text.split())
        answers_dict[label.lower()] = clean_text

    if not matches and ans_block.strip():
        single_answer = " ".join(ans_block.split())
        answers_dict["all"] = single_answer

    return answers_dict


# ----------------------------------------
# Metadata extractor from blob
# ----------------------------------------
def extract_details_from_blob(blob_data: bytes):
    """Extract structured details from PDF blob with clean department, subject, and issuing_person."""
    try:
        with pdfplumber.open(io.BytesIO(blob_data)) as pdf:
            all_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return {}, []

    all_text = all_text.replace("†", "*")
    lines = [ln.strip() for ln in all_text.splitlines() if ln.strip()]

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
            details["house"] = "Lok Sabha" if "LOK" in house_name else "Rajya Sabha"
            break

    # Department (lines above House)
    if details["house"]:
        house_idx = next(i for i, l in enumerate(lines) if house_pat.search(l))
        dept_lines = []
        for j in range(house_idx - 1, -1, -1):
            if lines[j].strip() == "" or "GOVERNMENT OF INDIA" in lines[j].upper():
                break
            dept_lines.insert(0, lines[j])
        details["department"] = " ".join(dept_lines).replace("GOVERNMENT OF INDIA", "").strip()

    # Question Number
    qpat = re.compile(r"(?:STARRED|UNSTARRED)?\s*QUESTION\s*NO\.?\s*[#†*]*[:\-]?\s*(\d+)", re.I)
    for line in lines:
        m = qpat.search(line)
        if m:
            details["question_number"] = m.group(1)
            break
    if not details["question_number"]:
        m = re.search(r"[#†*]*\s*(\d{1,4})\s*[:.\-]?\s*(?:Shri|Smt\.?|Dr\.?|Prof\.?|Kumari|Km\.?|Ms\.?|Miss)?", all_text, re.I)
        if m:
            details["question_number"] = m.group(1)

    # MP Names
    details["mp_name"] = ", ".join(extract_mp_names(all_text)) if all_text else None

    # Answered On
    date_match = DATE_RE.search(all_text)
    details["answered_on"] = _parse_date_flexible(date_match.group(0)) if date_match else None

    # Subject
    answered_on_match = re.search(r"TO BE ANSWERED ON\s*\d{1,2}[.\-\/]\d{1,2}[.\-\/]\d{2,4}", all_text, re.I)
    if answered_on_match:
        idx = answered_on_match.end()
        remaining = all_text[idx:].strip()
        remaining = re.sub(r"^\s*\d+\.\s*", "", remaining)
        subject_line = remaining.split("\n")[0].strip()
        details["subject"] = re.sub(r'[\[\]\*]', '', subject_line)

    # Issuing Person
    pattern = re.compile(r"ANSWER\s+THE\s+MINISTER\s+OF\s+[A-Z &]+?\s*\n(.*?)(?:\n|$)", re.I)
    match = pattern.search(all_text)
    if match:
        details["issuing_person"] = re.sub(r'[\[\]]', '', match.group(1)).strip()

    # Extract QA and Answers
    qa_pairs = extract_qa_pairs(all_text)
    answers = extract_answers(all_text)

    # Attach answers to questions
    for qa in qa_pairs:
        label = qa["sub_question_label"]
        qa["answer"] = answers.get(label) or answers.get("all") or None

    return details, qa_pairs


# ----------------------------------------
# DB Save Function
# ----------------------------------------
def process_blobs_and_save_metadata():
    """Fetch blobs from DB, extract metadata & QA, and save to metadata + qa_pairs tables."""
    try:
        conn = mysql.connector.connect(**db_config, database="parliament_data")
        cursor = conn.cursor(buffered=True)

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

            # Get metadata_id
            cursor.execute("SELECT id FROM metadata WHERE file_id = %s", (file_id,))
            metadata_id = cursor.fetchone()[0]

            # Save QA pairs
            for qa in qa_pairs:
                cursor.execute("""
                    INSERT INTO qa_pairs (metadata_id, sub_question_label, question, answer)
                    VALUES (%s, %s, %s, %s)
                """, (metadata_id, qa["sub_question_label"], qa["question"], qa.get("answer")))
            conn.commit()
            print(f"✅ Metadata + {len(qa_pairs)} QA pairs saved for file_id={file_id}")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")


# ✅ Standalone testing
if __name__ == "__main__":
    process_blobs_and_save_metadata()
