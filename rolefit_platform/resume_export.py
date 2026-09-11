import csv
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from copy import deepcopy
from xml.etree import ElementTree

from rolefit_platform.auto_tailor import CANONICAL_EDITABLE_RESUME_PATH, auto_tailor_job
from rolefit_platform.resume import ACTION_VERBS
from rolefit_platform.storage import get_job, list_jobs


DEFAULT_OUTPUT_DIR = "generated_resumes"
ATS_TEMPLATE_NAME = "Canonical ATS-safe single-column resume"
ATS_REQUIRED_SECTIONS = ["TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE", "PROJECTS", "EDUCATION", "CERTIFICATIONS & AWARDS"]
ATS_FORBIDDEN_MARKERS = {
    "tables": "<w:tbl", "drawings": "<w:drawing", "text boxes": "<w:txbxContent",
    "legacy graphics": "<w:pict", "embedded objects": "<w:object",
    "alternate rendered content": "<mc:AlternateContent",
}
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W = "{" + W_NS + "}"


def clean_filename(value):
    value = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_")
    return value[:90] or "resume"


def require_canonical_resume(path=None):
    path = path or CANONICAL_EDITABLE_RESUME_PATH or os.environ.get("ROLEFIT_CANONICAL_RESUME")
    if not path:
        raise FileNotFoundError(
            "No canonical resume template is configured. Set ROLEFIT_CANONICAL_RESUME "
            "to an ATS-safe one-page DOCX before exporting."
        )
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(path):
        raise FileNotFoundError("Canonical resume template not found: " + path)
    return path


def _register_namespaces(xml_bytes):
    for _, namespace in ElementTree.iterparse(io.BytesIO(xml_bytes), events=("start-ns",)):
        prefix, uri = namespace
        try:
            ElementTree.register_namespace(prefix or "", uri)
        except ValueError:
            pass


def _document_root(docx_path):
    with zipfile.ZipFile(docx_path) as docx:
        document = docx.read("word/document.xml")
    _register_namespaces(document)
    return ElementTree.fromstring(document)


def _paragraph_text(paragraph):
    return "".join(node.text or "" for node in paragraph.iter(W + "t")).strip()


def _is_bullet(paragraph):
    style = paragraph.find("./" + W + "pPr/" + W + "pStyle")
    if style is not None and style.get(W + "val") == "ListBullet":
        return True
    return paragraph.find("./" + W + "pPr/" + W + "numPr") is not None


def _replace_paragraph_text(paragraph, text):
    first_run = paragraph.find(W + "r")
    run_properties = deepcopy(first_run.find(W + "rPr")) if first_run is not None and first_run.find(W + "rPr") is not None else None
    for child in list(paragraph):
        if child.tag != W + "pPr":
            paragraph.remove(child)
    run = ElementTree.SubElement(paragraph, W + "r")
    if run_properties is not None:
        run.append(run_properties)
    ElementTree.SubElement(run, W + "t").text = text


def _body_children(root):
    body = root.find(W + "body")
    if body is None:
        raise ValueError("Canonical resume has no Word document body")
    return body, list(body)


def _find_index(children, text, start=0):
    for index in range(start, len(children)):
        if children[index].tag == W + "p" and text in _paragraph_text(children[index]):
            return index
    raise ValueError("Canonical resume slot not found: " + text)


def _current_role_bullets(root):
    _, children = _body_children(root)
    start = _find_index(children, "PROFESSIONAL EXPERIENCE") + 1
    first_bullet = next(
        (index for index in range(start, len(children)) if children[index].tag == W + "p" and _is_bullet(children[index])),
        None,
    )
    if first_bullet is None:
        raise ValueError("Canonical resume has no bullet group under PROFESSIONAL EXPERIENCE")
    end = first_bullet
    while end < len(children) and children[end].tag == W + "p" and _is_bullet(children[end]):
        end += 1
    return children[first_bullet:end]


def _replace_current_role_bullets(root, records):
    body, _ = _body_children(root)
    paragraphs = _current_role_bullets(root)
    if len(paragraphs) < len(records):
        raise ValueError("Canonical resume does not contain enough current-role bullet slots")
    for paragraph, record in zip(paragraphs, records):
        _replace_paragraph_text(paragraph, record["text"])
    for paragraph in paragraphs[len(records):]:
        body.remove(paragraph)


def _replace_all_bullets(root, records):
    _, children = _body_children(root)
    paragraphs = [node for node in children if node.tag == W + "p" and _is_bullet(node)]
    if len(paragraphs) != len(records):
        raise ValueError("Canonical seed has " + str(len(paragraphs)) + " bullets; expected " + str(len(records)))
    for paragraph, record in zip(paragraphs, records):
        _replace_paragraph_text(paragraph, record["text"])


def _project_groups(root):
    _, children = _body_children(root)
    start = _find_index(children, "PROJECTS") + 1
    end = _find_index(children, "EDUCATION", start)
    section = children[start:end]
    groups = {}
    index = 0
    while index < len(section):
        header = section[index]
        name = _paragraph_text(header).split(" | ", 1)[0].strip()
        group = [header]
        index += 1
        while index < len(section) and _is_bullet(section[index]):
            group.append(section[index])
            index += 1
        groups[name] = group
    return groups, start, end


def _replace_projects(root, projects):
    body, _ = _body_children(root)
    groups, start, end = _project_groups(root)
    children = list(body)
    for node in children[start:end]:
        body.remove(node)
    insert_at = start
    for project in projects:
        name = project.get("name") or ""
        if name not in groups:
            raise ValueError("Canonical project slot not found: " + name)
        group = groups[name]
        bullets = [node for node in group[1:] if _is_bullet(node)]
        records = project.get("bullet_records") or [
            {"text": text, "evidence_id": project.get("id") or name, "approved_variants": [text]}
            for text in project.get("bullets") or []
        ]
        if len(bullets) != len(records):
            raise ValueError("Project bullet count changed for " + name)
        for paragraph, record in zip(bullets, records):
            _replace_paragraph_text(paragraph, record["text"])
        for node in group:
            body.insert(insert_at, node)
            insert_at += 1


def _write_package(template_path, path, root):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # ElementTree omits declarations used only by mc:Ignorable, which makes
    # Microsoft Word report the otherwise valid package as unreadable.
    root.attrib.pop("{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable", None)
    document = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(template_path) as source, zipfile.ZipFile(path, "w") as target:
        for info in source.infolist():
            data = document if info.filename == "word/document.xml" else source.read(info.filename)
            target.writestr(info, data)


def _patch_template(template_path, path, records=None, projects=None, replace_all=False):
    root = _document_root(template_path)
    if replace_all:
        _replace_all_bullets(root, records or [])
    else:
        _replace_current_role_bullets(root, records or [])
        if projects:
            _replace_projects(root, projects)
    _write_package(template_path, path, root)


def _docx_paragraphs(path):
    root = _document_root(path)
    paragraphs, bullets = [], []
    for node in root.iter(W + "p"):
        text = _paragraph_text(node)
        if text:
            paragraphs.append(text)
            if _is_bullet(node):
                bullets.append(text)
    return paragraphs, bullets


def _hyperlinks(path):
    with zipfile.ZipFile(path) as docx:
        try:
            relationships = docx.read("word/_rels/document.xml.rels")
        except KeyError:
            return []
        root = ElementTree.fromstring(relationships)
    return sorted(node.get("Target") for node in root.findall("{" + REL_NS + "}Relationship") if node.get("Type", "").endswith("/hyperlink"))


def _package_fidelity(template_path, path):
    errors = []
    with zipfile.ZipFile(template_path) as source, zipfile.ZipFile(path) as output:
        source_names, output_names = set(source.namelist()), set(output.namelist())
        if source_names != output_names:
            errors.append("DOCX package parts changed")
        for name in sorted(source_names & output_names):
            if name != "word/document.xml" and hashlib.sha256(source.read(name)).digest() != hashlib.sha256(output.read(name)).digest():
                errors.append("canonical package part changed: " + name)
    if _hyperlinks(template_path) != _hyperlinks(path):
        errors.append("canonical hyperlinks changed")
    return errors


def _command_path(environment_name, executable):
    configured = os.environ.get(environment_name)
    if configured:
        return configured
    if executable == "soffice":
        python_root = os.path.dirname(os.path.dirname(sys.executable))
        runtime_candidate = os.path.join(os.path.dirname(python_root), "bin", "override", "soffice")
        home_candidate = os.path.expanduser("~/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice")
        for candidate in [runtime_candidate, home_candidate]:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    found = shutil.which(executable)
    if not found:
        raise RuntimeError(executable + " is required for rendered resume validation")
    return found


def render_docx(path, pdf_path=None):
    soffice = _command_path("ROLEFIT_SOFFICE", "soffice")
    output_dir = os.path.dirname(os.path.abspath(pdf_path)) if pdf_path else tempfile.mkdtemp(prefix="rolefit-render-")
    os.makedirs(output_dir, exist_ok=True)
    profile_dir = tempfile.mkdtemp(prefix="rolefit-lo-profile-")
    result = subprocess.run(
        [soffice, "-env:UserInstallation=file://" + profile_dir, "--headless", "--convert-to", "pdf", "--outdir", output_dir, os.path.abspath(path)],
        check=False, capture_output=True, text=True, timeout=60,
    )
    generated = os.path.join(output_dir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    if result.returncode or not os.path.isfile(generated):
        raise RuntimeError("LibreOffice resume render failed: " + (result.stderr or result.stdout).strip())
    if pdf_path and os.path.abspath(generated) != os.path.abspath(pdf_path):
        shutil.copyfile(generated, pdf_path)
        generated = os.path.abspath(pdf_path)
    return generated


def _normalize_line(text):
    return " ".join(text.replace("•", " ").split()).strip()


def validate_rendered_resume(docx_path, bullet_texts, pdf_path=None):
    rendered_pdf = render_docx(docx_path, pdf_path)
    info = subprocess.run([_command_path("ROLEFIT_PDFINFO", "pdfinfo"), rendered_pdf], check=True, capture_output=True, text=True, timeout=30).stdout
    page_match = re.search(r"^Pages:\s+(\d+)", info, flags=re.MULTILINE)
    page_count = int(page_match.group(1)) if page_match else 0
    layout = subprocess.run([_command_path("ROLEFIT_PDFTOTEXT", "pdftotext"), "-layout", rendered_pdf, "-"], check=True, capture_output=True, text=True, timeout=30).stdout
    lines = [_normalize_line(line) for line in layout.splitlines() if _normalize_line(line)]
    offending = [text for text in bullet_texts if not any(_normalize_line(text) in line for line in lines)]
    missing_sections = [section for section in ATS_REQUIRED_SECTIONS if not any(section in line for line in lines)]
    bbox = subprocess.run([_command_path("ROLEFIT_PDFTOTEXT", "pdftotext"), "-bbox-layout", rendered_pdf, "-"], check=True, capture_output=True, text=True, timeout=30).stdout
    bbox_root = ElementTree.fromstring(bbox)
    overflow_words = []
    for page in bbox_root.iter("{http://www.w3.org/1999/xhtml}page"):
        width, height = float(page.get("width", "0")), float(page.get("height", "0"))
        for word in page.iter("{http://www.w3.org/1999/xhtml}word"):
            x_min, y_min = float(word.get("xMin", "0")), float(word.get("yMin", "0"))
            x_max, y_max = float(word.get("xMax", "0")), float(word.get("yMax", "0"))
            if x_min < -0.5 or y_min < -0.5 or x_max > width + 0.5 or y_max > height + 0.5:
                overflow_words.append(word.text or "")
    return {
        "passed": page_count == 1 and not offending and not missing_sections and not overflow_words,
        "pdf_path": rendered_pdf, "page_count": page_count, "one_page": page_count == 1,
        "bullet_line_count": len(bullet_texts), "one_line_bullets": len(bullet_texts) - len(offending),
        "offending_bullets": offending, "missing_sections": missing_sections, "overflow_words": overflow_words,
        "word_render_note": "LibreOffice validation passed; final application copies should still receive a quick Microsoft Word visual check.",
    }


def validate_ats_docx(path, template_path=None, render=True, pdf_path=None):
    errors = []
    try:
        with zipfile.ZipFile(path) as docx:
            names = set(docx.namelist())
            required_parts = {"[Content_Types].xml", "word/document.xml", "word/styles.xml"}
            missing_parts = sorted(required_parts - names)
            if missing_parts:
                return {"passed": False, "errors": ["missing DOCX parts: " + ", ".join(missing_parts)], "plain_text": ""}
            document = docx.read("word/document.xml").decode("utf-8")
            styles = docx.read("word/styles.xml").decode("utf-8")
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, KeyError) as exc:
        return {"passed": False, "errors": ["invalid DOCX package: " + str(exc)], "plain_text": ""}
    for label, marker in ATS_FORBIDDEN_MARKERS.items():
        if marker in document:
            errors.append("contains " + label)
    paragraphs, bullets = _docx_paragraphs(path)
    plain_text = "\n".join(paragraphs)
    for section in ATS_REQUIRED_SECTIONS:
        if section not in paragraphs:
            errors.append("missing section heading: " + section)
    if len(plain_text) < 500:
        errors.append("insufficient machine-readable text")
    if "Times New Roman" not in styles:
        errors.append("canonical Times New Roman styles are missing")
    for bullet in bullets:
        verb = bullet.split()[0] if bullet.split() else ""
        if verb not in ACTION_VERBS:
            errors.append("bullet does not begin with an approved action verb: " + bullet)
    if template_path:
        errors.extend(_package_fidelity(template_path, path))
    rendered = None
    if render and not errors:
        rendered = validate_rendered_resume(path, bullets, pdf_path)
        if not rendered["one_page"]:
            errors.append("rendered resume is " + str(rendered["page_count"]) + " pages; expected exactly one")
        errors.extend("bullet wraps or is clipped: " + bullet for bullet in rendered["offending_bullets"])
        errors.extend("rendered section missing: " + section for section in rendered["missing_sections"])
        if rendered["overflow_words"]:
            errors.append("rendered text exceeds page bounds: " + ", ".join(rendered["overflow_words"][:10]))
    return {"passed": not errors, "errors": errors, "plain_text": plain_text, "structure": "single-column canonical DOCX", "hyperlinks": _hyperlinks(path), "rendered": rendered}


def _all_editable_records(records, projects):
    values = list(records)
    for project in projects or []:
        values.extend(project.get("bullet_records") or [])
    return values


def _next_shorter_variant(record):
    current = record["text"]
    candidates = sorted((value for value in record.get("approved_variants") or [] if len(value) < len(current)), key=len, reverse=True)
    for candidate in candidates:
        if record.get("metric_must_preserve") and any(metric.lower() not in candidate.lower() for metric in record.get("approved_metrics") or []):
            continue
        return candidate
    return None


def write_docx(path, job, tailoring, template_path=CANONICAL_EDITABLE_RESUME_PATH):
    del job
    template_path = require_canonical_resume(template_path)
    records = deepcopy(tailoring.get("rewritten_bullet_records") or [])
    if not records:
        records = [{"evidence_id": "legacy", "text": text, "approved_variants": [text]} for text in tailoring.get("rewritten_bullets") or []]
    projects = deepcopy(tailoring.get("projects") or [])
    for _ in range(8):
        _patch_template(template_path, path, records, projects)
        validation = validate_ats_docx(path, template_path, render=True)
        if validation["passed"]:
            return validation
        offenders = {_normalize_line(value) for value in (validation.get("rendered") or {}).get("offending_bullets") or []}
        changed = False
        for record in _all_editable_records(records, projects):
            if _normalize_line(record.get("text") or "") in offenders:
                replacement = _next_shorter_variant(record)
                if replacement:
                    record["text"] = replacement
                    changed = True
        if not changed:
            evidence = [record.get("evidence_id") or "unknown" for record in _all_editable_records(records, projects) if _normalize_line(record.get("text") or "") in offenders]
            detail = ", ".join(evidence) if evidence else "; ".join(validation["errors"])
            raise ValueError("Resume render validation failed; no approved one-line variant remains for: " + detail)
    raise ValueError("Resume render validation failed after approved concise-variant retries")


def export_job_resume(db_path, job_id, output_dir=DEFAULT_OUTPUT_DIR):
    job = get_job(db_path, job_id)
    if not job:
        return None
    template = require_canonical_resume()
    tailoring = auto_tailor_job(db_path, job_id, template)
    if not tailoring:
        return None
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    filename = clean_filename(str(job["id"]) + "_" + (job.get("company") or "") + "_" + (job.get("role") or "")) + ".docx"
    path = os.path.join(output_dir, filename)
    validation = write_docx(path, job, tailoring, template)
    return {"job_id": job["id"], "company": job.get("company"), "role": job.get("role"), "path": path, "template_source": template, "template_name": ATS_TEMPLATE_NAME, "ats_validation": validation}


def export_finished_resumes(db_path, output_dir=DEFAULT_OUTPUT_DIR, limit=25):
    rows = list_jobs(db_path, limit)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    exported = [item for item in (export_job_resume(db_path, job["id"], output_dir) for job in rows) if item]
    index_path = os.path.join(output_dir, "index.csv")
    with open(index_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["job_id", "company", "role", "path"])
        writer.writeheader()
        for row in exported:
            writer.writerow({key: row.get(key) for key in writer.fieldnames})
    return {"output_dir": output_dir, "index": index_path, "exported": exported, "count": len(exported)}
