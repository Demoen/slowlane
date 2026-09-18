from __future__ import annotations

import sys
import tomllib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


class Document(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if value := attributes.get("id"):
            self.ids.add(value)
        if tag == "a" and (value := attributes.get("name")):
            self.ids.add(value)
        for field in ("href", "src"):
            if value := attributes.get(field):
                self.links.append(value)


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    config = tomllib.loads((project_root / "zensical.toml").read_text(encoding="utf-8"))["project"]
    site = (project_root / config.get("site_dir", "site")).resolve()
    base_url = config["site_url"].rstrip("/") + "/"
    base = urlsplit(base_url)
    documents = {path: Document(path.read_text(encoding="utf-8")) for path in site.rglob("*.html")}
    if not documents or not (site / "index.html").is_file():
        print("Documentation output is missing. Run zensical build first.", file=sys.stderr)
        return 1

    failures: list[str] = []
    checked = 0
    for path, document in documents.items():
        relative = path.relative_to(site).as_posix()
        page_url = base_url + relative.removesuffix("index.html")
        for link in document.links:
            url = urlsplit(urljoin(page_url, link))
            if url.scheme not in {"https", "http"} or url.netloc != base.netloc:
                continue
            checked += 1
            problem = ""
            if not url.path.startswith(base.path):
                problem = "outside the site URL prefix"
            else:
                target = (site / unquote(url.path[len(base.path) :])).resolve()
                if not target.is_relative_to(site):
                    problem = "outside the output directory"
                else:
                    if target.is_dir():
                        target /= "index.html"
                    if not target.is_file():
                        problem = "missing file"
                    elif (
                        url.fragment
                        and target in documents
                        and unquote(url.fragment) not in documents[target].ids
                    ):
                        problem = "missing anchor"
            if problem:
                failures.append(f"{relative}: {link!r}: {problem}")

    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"Checked {len(documents)} pages and {checked} internal links/assets.")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
