import csv
import os
import re
import zipfile
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from rolefit_platform.auto_tailor import auto_tailor_job
from rolefit_platform.storage import get_job, get_tailored_resume, list_jobs


DEFAULT_OUTPUT_DIR = "generated_resumes"
ATS_TEMPLATE_NAME = "ATS-safe single-column resume"
ATS_REQUIRED_SECTIONS = [
    "TECHNICAL SKILLS",
    "PROFESSIONAL EXPERIENCE",
    "PROJECTS",
    "EDUCATION",
    "CERTIFICATIONS & AWARDS",
]
ATS_FORBIDDEN_MARKERS = {
    "tables": "<w:tbl",
    "drawings": "<w:drawing",
    "text boxes": "<w:txbxContent",
    "legacy graphics": "<w:pict",
    "embedded objects": "<w:object",
    "alternate rendered content": "<mc:AlternateContent",
}


def clean_filename(value):
    value = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_")
    return value[:90] or "resume"


def xml_text(value):
    return escape(str(value or ""))


def clean_bullet_text(value):
    text = str(value or "").strip()
    while text.endswith("."):
        text = text[:-1].rstrip()
    return text


def run_xml(text="", bold=False, italic=False, size=None):
    props = []
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    if size:
        props.append('<w:sz w:val="' + str(size * 2) + '"/>')
    rpr = "<w:rPr>" + "".join(props) + "</w:rPr>" if props else ""
    return "<w:r>" + rpr + "<w:t xml:space=\"preserve\">" + xml_text(text) + "</w:t></w:r>"


def tab_run():
    return "<w:r><w:tab/></w:r>"


def paragraph(text="", style=None, bullet=False, bold=False, italic=False, size=None, align=None, border=False, spacing_after=0, spacing_before=0, keep_next=False):
    if bullet:
        text = clean_bullet_text(text)
    return paragraph_runs([{"text": text, "bold": bold, "italic": italic, "size": size}], style, bullet, align, border, spacing_after=spacing_after, spacing_before=spacing_before, keep_next=keep_next)


def paragraph_runs(runs, style=None, bullet=False, align=None, border=False, tab_right=False, spacing_after=0, spacing_before=0, keep_next=False):
    props = []
    if style:
        props.append('<w:pStyle w:val="' + style + '"/>')
    if keep_next:
        props.append("<w:keepNext/>")
    if bullet:
        props.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')
    if border:
        props.append('<w:pBdr><w:bottom w:val="single" w:sz="8" w:space="1" w:color="000000"/></w:pBdr>')
    if tab_right:
        props.append('<w:tabs><w:tab w:val="right" w:pos="10800"/></w:tabs>')
    props.append('<w:spacing w:before="' + str(spacing_before) + '" w:after="' + str(spacing_after) + '" w:line="216" w:lineRule="auto"/>')
    if align:
        props.append('<w:jc w:val="' + align + '"/>')
    ppr = "<w:pPr>" + "".join(props) + "</w:pPr>" if props else ""
    body = []
    for item in runs:
        if item.get("tab"):
            body.append(tab_run())
        else:
            body.append(run_xml(item.get("text", ""), item.get("bold", False), item.get("italic", False), item.get("size")))
    return "<w:p>" + ppr + "".join(body) + "</w:p>"


def section_properties():
    return """
<w:sectPr>
  <w:pgSz w:w="12240" w:h="15840"/>
  <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="360" w:footer="360" w:gutter="0"/>
</w:sectPr>
"""


def section_heading(text):
    return paragraph(text, style="Heading1", border=True, spacing_before=120, spacing_after=0, keep_next=True)


def skill_line(label, text):
    return paragraph_runs([
        {"text": label + ": ", "bold": True, "size": 10},
        {"text": text, "size": 10},
    ], spacing_after=0)


def company_line(company, location=None):
    if location:
        return paragraph_runs([
            {"text": company, "bold": True, "size": 10},
            {"text": " | " + location, "size": 10},
        ], spacing_after=0, keep_next=True)
    return paragraph(company, bold=True, size=10, spacing_after=0, keep_next=True)


def role_line(title, date, trailing=None):
    runs = [{"text": title, "italic": True, "size": 10}]
    if trailing:
        runs.append({"text": " | " + trailing, "size": 10})
    runs.extend([{"tab": True}, {"text": date, "size": 10}])
    return paragraph_runs(runs, tab_right=True, spacing_after=0, keep_next=True)


def project_line(name, label, date):
    return paragraph_runs([
        {"text": name, "bold": True, "size": 10},
        {"text": " | ", "size": 10},
        {"text": label, "italic": True, "size": 10},
        {"tab": True},
        {"text": date, "size": 10},
    ], tab_right=True, spacing_after=0, keep_next=True)


def education_line(school, date):
    return paragraph_runs([
        {"text": school, "bold": True, "size": 10},
        {"tab": True},
        {"text": date, "size": 10},
    ], tab_right=True, spacing_after=0, keep_next=True)


def document_xml(job, tailoring):
    role = job.get("role") or "Software Engineer"
    company = job.get("company") or "Target Company"
    bullets = tailoring.get("rewritten_bullets") or []
    projects = tailoring.get("projects") or []
    if not projects:
        from rolefit_platform.resume import tailored_projects
        projects = tailored_projects(" ".join([role, company, job.get("description") or ""]))

    parts = []
    parts.append(paragraph("Sample Candidate", bold=True, size=18, align="center", spacing_after=0))
    parts.append(paragraph("Austin, TX | sample@example.com | portfolio.example.com | linkedin.com/in/sample | github.com/sample", size=10, align="center", spacing_after=160))

    parts.append(section_heading("TECHNICAL SKILLS"))
    parts.append(skill_line("Languages", "Python, Java, C++, SQL, Go"))
    parts.append(skill_line("Infrastructure & Cloud", "Public cloud, Docker, Terraform, Linux"))
    parts.append(skill_line("Testing & Automation", "PyTest, CI/CD, Canary Testing"))
    parts.append(skill_line("Data & Observability", "Metric pipelines, Alerting, MQL, PostgreSQL"))

    parts.append(section_heading("PROFESSIONAL EXPERIENCE"))
    parts.append(company_line("Cloud Infrastructure Platform"))
    parts.append(role_line("Software Engineer, Dataplane Systems", "2025 - Present", "Austin, TX"))
    for item in bullets[:5]:
        parts.append(paragraph(item, bullet=True, size=10, spacing_after=0))

    parts.append(role_line("Software Engineer Intern, Cloud Storage Platform", "Summer 2024", "Seattle, WA"))
    parts.append(paragraph("Designed and deployed a metrics pipeline ingesting 50+ tenant-level object storage replication and copy-service signals for network and latency analysis", bullet=True, size=10, spacing_after=0))
    parts.append(paragraph("Authored 50+ MQL-based monitors to isolate replication and networking issues, reducing fault localization time by ~40%", bullet=True, size=10, spacing_after=80))

    parts.append(role_line("Software Engineer Intern, Infrastructure Reliability", "Summer 2023", "Austin, TX"))
    parts.append(paragraph("Built a real-time PSU fault detection system, reducing mean detection time by ~60%, and enabling live repair services", bullet=True, size=10, spacing_after=0))
    parts.append(paragraph("Verified fault scenarios across 3+ hardware generations, supporting migration to non-terminating VM repair models", bullet=True, size=10, spacing_after=80))

    parts.append(company_line("Carleton College", "Northfield, MN"))
    parts.append(role_line("Computer Science Course Staff and Lab Assistant", "Sept 2022 – Sep 2024"))
    parts.append(paragraph("Mentored 50+ students in algorithms, computer systems, and computer architecture", bullet=True, size=10, spacing_after=0))
    parts.append(paragraph("Supported coursework on pipelining, cache design, and low-level performance reasoning", bullet=True, size=10, spacing_after=80))

    parts.append(section_heading("PROJECTS"))
    for project in projects[:3]:
        parts.append(project_line(project.get("name"), project.get("label"), project.get("date")))
        project_bullets = project.get("bullets") or []
        for index, item in enumerate(project_bullets[:2]):
            spacing = 80 if index == len(project_bullets[:2]) - 1 else 0
            parts.append(paragraph(item, bullet=True, size=10, spacing_after=spacing))

    parts.append(section_heading("EDUCATION"))
    parts.append(education_line("Graduate Computer Science Program", "In progress"))
    parts.append(paragraph_runs([
        {"text": "Master of Science", "bold": True, "size": 10},
        {"text": " in Computer Science", "size": 10},
    ], spacing_after=80))
    parts.append(education_line("Undergraduate Computer Science Program", "Graduated"))
    parts.append(paragraph_runs([
        {"text": "Bachelor of Arts", "bold": True, "size": 10},
        {"text": " in Computer Science", "size": 10},
    ], spacing_after=0))
    parts.append(paragraph_runs([
        {"text": "Activities: ", "bold": True, "size": 10},
        {"text": "Systems programming, distributed systems, and infrastructure coursework", "size": 10},
    ], spacing_after=80))

    parts.append(section_heading("CERTIFICATIONS & AWARDS"))
    parts.append(paragraph("Certifications: Cloud infrastructure foundations certification", size=10, spacing_after=0))
    parts.append(paragraph("Awards: Academic and leadership recognitions", size=10, spacing_after=0))

    body = "".join(parts) + section_properties()
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>""" + body + """</w:body>
</w:document>"""


def styles_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:after="40" w:line="216" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="160" w:after="0"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="24"/></w:rPr>
  </w:style>
</w:styles>"""


def numbering_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:multiLevelType w:val="hybridMultilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="•"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:hint="default"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>"""


def settings_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
  <w:compat>
    <w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/>
  </w:compat>
</w:settings>"""


def write_docx(path, job, tailoring):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>""")
        docx.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        docx.writestr("word/_rels/document.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>""")
        docx.writestr("word/document.xml", document_xml(job, tailoring))
        docx.writestr("word/styles.xml", styles_xml())
        docx.writestr("word/numbering.xml", numbering_xml())
        docx.writestr("word/settings.xml", settings_xml())
    validation = validate_ats_docx(path)
    if not validation["passed"]:
        raise ValueError("ATS validation failed: " + "; ".join(validation["errors"]))
    return validation


def validate_ats_docx(path):
    errors = []
    try:
        with zipfile.ZipFile(path) as docx:
            names = set(docx.namelist())
            required_parts = {"[Content_Types].xml", "word/document.xml", "word/styles.xml"}
            missing_parts = sorted(required_parts - names)
            if missing_parts:
                errors.append("missing DOCX parts: " + ", ".join(missing_parts))
                return {"passed": False, "errors": errors, "plain_text": ""}
            document = docx.read("word/document.xml").decode("utf-8")
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        return {"passed": False, "errors": ["invalid DOCX package: " + str(exc)], "plain_text": ""}

    for label, marker in ATS_FORBIDDEN_MARKERS.items():
        if marker in document:
            errors.append("contains " + label)

    try:
        root = ElementTree.fromstring(document)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = []
        for node in root.iter(namespace + "p"):
            text = "".join(item.text or "" for item in node.iter(namespace + "t")).strip()
            if text:
                paragraphs.append(text)
        plain_text = "\n".join(paragraphs)
    except ElementTree.ParseError as exc:
        return {"passed": False, "errors": ["invalid document XML: " + str(exc)], "plain_text": ""}

    for section in ATS_REQUIRED_SECTIONS:
        if section not in paragraphs:
            errors.append("missing section heading: " + section)
    if len(plain_text) < 500:
        errors.append("insufficient machine-readable text")

    return {
        "passed": not errors,
        "errors": errors,
        "plain_text": plain_text,
        "structure": "single-column plain-text DOCX",
    }


def export_job_resume(db_path, job_id, output_dir=DEFAULT_OUTPUT_DIR):
    job = get_job(db_path, job_id)
    if not job:
        return None
    tailoring = get_tailored_resume(db_path, job_id)
    source = (tailoring or {}).get("resume_source")
    if source and os.path.isfile(os.path.expanduser(source)):
        tailoring = auto_tailor_job(db_path, job_id, source)
    elif not tailoring:
        tailoring = auto_tailor_job(db_path, job_id)
    if not tailoring:
        return None
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    filename = clean_filename(str(job["id"]) + "_" + (job.get("company") or "") + "_" + (job.get("role") or "")) + ".docx"
    path = os.path.join(output_dir, filename)
    validation = write_docx(path, job, tailoring)
    return {
        "job_id": job["id"],
        "company": job.get("company"),
        "role": job.get("role"),
        "path": path,
        "template_name": ATS_TEMPLATE_NAME,
        "ats_validation": validation,
    }


def export_finished_resumes(db_path, output_dir=DEFAULT_OUTPUT_DIR, limit=25):
    rows = list_jobs(db_path, limit)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    exported = []
    for job in rows:
        item = export_job_resume(db_path, job["id"], output_dir)
        if item:
            exported.append(item)
    index_path = os.path.join(output_dir, "index.csv")
    with open(index_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["job_id", "company", "role", "path"])
        writer.writeheader()
        for row in exported:
            writer.writerow(row)
    return {"output_dir": output_dir, "index": index_path, "exported": exported, "count": len(exported)}
