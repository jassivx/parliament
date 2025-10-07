import re
import io
from datetime import date
import mysql.connector
from config.db_config import db_config
from PyPDF2 import PdfReader

# ----------------------------------------
# Helpers
# ----------------------------------------
DATE_RE = re.compile(r"(\d{1,2}\s*[.\-\/]\s*\d{1,2}\s*[.\-\/]\s*\d{2,4})")


def _parse_date_flexible(raw: str):
    """Normalize a date string like '25 .11.2024' or '25-11-24' to a Python date."""
    if not raw:
        return None
    s = re.sub(r"\s*([.\-\/])\s*", r"\1", raw.strip())
    m = re.match(r"^(\d{1,2})[.\-\/](\d{1,2})[.\-\/](\d{2,4})$", s)
    if not m:
        return None
    d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000 if y < 50 else 1900
    try:
        return date(y, mth, d)
    except ValueError:
        return None


# ----------------------------------------
# 👤 MP Names Extractor
# ----------------------------------------
TITLE_TOKENS = r"(Shri|Smt\.?|Dr\.?|Prof\.?|Kumari|Km\.?|Ms\.?|Miss|Thiru|Thirumathi)"


def extract_mp_names(full_text: str):
    """Extract MP names from PDF text, starting after subject and question number, ending before 'Will the Minister'."""
    text = full_text.replace("†", "*")
    text = re.sub(r"[ \t\r\f]+", " ", text)
    text = re.sub(r"\n+", " ", text)

    # Find subject, question number, and names until 'Will the Minister'
    qnum_pat = re.compile(
        r"(?:STARRED|UNSTARRED)?\s*QUESTION\s*NO\.?\s*[†*]?\s*(\d{1,4})\s*[.:]?\s*([^:]*?)\s*:\s*Will the Minister",
        re.I | re.S
    )

    m = qnum_pat.search(text)
    if not m:
        return []

    block = m.group(2).strip()
    if not block:
        return []

    # Normalize the block
    block = re.sub(r"\bAND\b", ",", block, flags=re.I)
    block = re.sub(r"[\s,;]+$", "", block)

    # Extract names, optionally preceded by titles
    name_pat = re.compile(
        rf"(?:{TITLE_TOKENS}\s+)?([A-Z][\w\.'-]*(?:\s+[A-Z][\w\.'-]*){{0,6}})",
        re.I
    )
    found = []
    for match in name_pat.finditer(block):
        nm = match.group(0).strip()
        nm = re.sub(r"[\s,;]+$", "", nm)
        found.append(nm)

    # Deduplicate names
    seen, result = set(), []
    for n in found:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            result.append(n)
    return result


# ----------------------------------------
# 📄 Metadata Extractor
# ----------------------------------------
def extract_details_from_blob(blob_data: bytes):
    """Extract structured details from a PDF blob."""
    try:
        reader = PdfReader(io.BytesIO(blob_data))
        all_text = "\n".join(page.extract_text() or "" for page in reader.pages)
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
    for line in lines:
        u = line.upper()
        if "LOK SABHA" in u:
            details["house"] = "Lok Sabha";
            break
        if "RAJYA SABHA" in u:
            details["house"] = "Rajya Sabha";
            break

    # Department
    for i, line in enumerate(lines):
        if details["house"] and details["house"].upper() in line.upper():
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
        if "ANSWERED ON" in line.upper():
            look, nxt = line, (lines[i + 1] if i + 1 < len(lines) else "")
            m = DATE_RE.search(look) or DATE_RE.search(nxt) or DATE_RE.search(look + " " + nxt)
            details["answered_on"] = _parse_date_flexible(m.group(1)) if m else None

            k = i + 1
            while k < len(lines):
                if "ANSWERED ON" in lines[k].upper(): k += 1; continue
                if DATE_RE.search(lines[k]) or re.fullmatch(r"[-–—:]+", lines[k]): k += 1; continue
                if lines[k].strip():
                    details["subject"] = lines[k].strip()[:500];
                    break
                k += 1
            answered_found = True
            break

    if not answered_found and not details["subject"]:
        for i, line in enumerate(lines):
            if re.search(r"(?:STARRED|UNSTARRED)?\s*QUESTION\s*NO\.?", line, re.I):
                k = i + 1
                while k < len(lines):
                    if "ANSWERED ON" in lines[k].upper():
                        kk = k + 1
                        while kk < len(lines) and (
                                DATE_RE.search(lines[kk]) or "ANSWERED ON" in lines[kk].upper() or re.fullmatch(
                                r"[-–—:]+", lines[kk])):
                            kk += 1
                        if kk < len(lines):
                            details["subject"] = lines[kk].strip()[:500]
                        break
                    if DATE_RE.search(lines[k]) or re.fullmatch(r"[-–—:]+", lines[k]) or not lines[k].strip():
                        k += 1;
                        continue
                    details["subject"] = lines[k].strip()[:500];
                    break
                break

    # Question Number
    qnum_pat = re.compile(r"(?:STARRED|UNSTARRED)?\s*QUESTION\s*NO\.?\s*[†*]?\s*(\d+)", re.I)
    for line in lines:
        m = qnum_pat.search(line)
        if m:
            details["question_number"] = m.group(1);
            break
    if not details["question_number"]:
        m = re.search(r"[†*]?\s*(\d{1,4})\s*[:.\-]?\s+", all_text, re.I)
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
    details["issuing_person"] = match.group(1).strip() if match else None

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