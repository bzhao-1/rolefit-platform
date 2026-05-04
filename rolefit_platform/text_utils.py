import html.parser
import re
import urllib.request


class TextExtractor(html.parser.HTMLParser):
    def __init__(self):
        html.parser.HTMLParser.__init__(self)
        self.parts = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            value = data.strip()
            if value:
                self.parts.append(value)


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()


def words(text):
    return re.findall(r"[a-z0-9+#.-]+", (text or "").lower())


def count_matches(text, terms):
    lower = (text or "").lower()
    found = []
    for term in terms:
        needle = term.lower()
        if re.match(r"^[a-z0-9]+$", needle):
            pattern = r"\b" + re.escape(needle) + r"s?\b"
            matched = re.search(pattern, lower)
        else:
            matched = needle in lower
        if matched:
            found.append(term)
    return found


def load_text_from_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rolefit-platform/0.1"})
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(2_000_000)
        content_type = response.headers.get("content-type", "")
    if "text/html" in content_type or raw.lstrip().startswith(b"<"):
        parser = TextExtractor()
        parser.feed(raw.decode("utf-8", errors="ignore"))
        return normalize(" ".join(parser.parts))
    return normalize(raw.decode("utf-8", errors="ignore"))


def load_job_text(args):
    if args.text:
        return args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8") as handle:
            return handle.read()
    if args.url:
        return load_text_from_url(args.url)
    return ""


def compact_lines(lines):
    return "\n".join(line.strip() for line in lines if line and line.strip())
