# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "commonmark",
#     "flask",
#     "typer",
# ]
# ///


import json
import os
import re
from pathlib import Path

import commonmark
import typer
from flask import Flask, send_file

OUTPUT_FILE = "combined_chat_history.md"


def collect_failed_histories(base_dir: Path, output_file):
    first_try = 0
    second_try = 0
    failures = 0
    total = 0
    all_roots = []
    for root, _, files in os.walk(str(base_dir)):
        if ".aider.results.json" in files and ".aider.chat.history.md" in files:
            all_roots.append(root)

    all_roots = list(sorted(all_roots))
    with open(output_file, "w") as outfile:
        for root in all_roots:
            results_path = os.path.join(root, ".aider.results.json")
            results = json.load(open(results_path))
            test_outcomes = results.get("tests_outcomes", [])
            total += 1
            if test_outcomes[0]:
                first_try += 1
                second_try += 1
                continue
            if test_outcomes[1]:
                second_try += 1
                continue

            failures += 1
            history_path = os.path.join(root, ".aider.chat.history.md")
            with open(history_path, "r") as history_file:
                outfile.write(f"## Chat History for {root}\n\n")
                outfile.write(history_file.read())
                outfile.write("\n\n---\n\n")
                print(f"Added chat history from {history_path}")

    print(f"First try: {first_try / total * 100:.2f}%")
    print(f"Second try: {second_try / total * 100:.2f}%")
    print(f"Failures: {failures / total * 100:.2f}%")
    print(f"Combined history written to {output_file}")


def cleanup_md(input_md_file, output_md_file):
    # Read markdown content
    with open(input_md_file, "r") as f:
        content = f.read()

    # Convert ```text blocks to regular code blocks
    content = re.sub(r"```text\n(.*?)```", r"```\n\1```", content, flags=re.DOTALL)

    # Convert diff blocks
    def format_diff(match):
        if "SEARCH" not in match.group(0) or "REPLACE" not in match.group(0):
            return match.group(0)

        diff_content = match.group(1)
        formatted = []
        formatted.append("<div class='diff-remove'>")
        found_add = False
        for line in diff_content.split("\n"):
            if "=======" in line:
                found_add = True
                formatted.append('</div><div class="diff-add">')
                continue
            if "<<<<<<< SEARCH" in line or ">>>>>>> REPLACE" in line:
                continue
            formatted.append(line)

        if not found_add:
            formatted.append('</div><div class="diff-add"></div>')
        return '<pre><div class="diff-block">' + "\n".join(formatted) + "</div></pre>"

    append = r"#### Instructions append.*\n(####.*\n)*"
    content = re.sub(append, "*GO.*", content, flags=re.MULTILINE | re.DOTALL)
    # find code blocks and format with dif*GO.*f
    content = re.sub(r"```[a-z]*\n(.*?)```", format_diff, content, flags=re.DOTALL)
    content = re.sub(r"^####[\s]", "", content, flags=re.MULTILINE)
    content = re.sub(
        r"""====
FAIL: (.*)
----""",
        r"""### FAIL: \1""",
        content,
    )

    with open(output_md_file, "w") as f:
        f.write(content)


def convert_to_html(input_md_file, output_html_file: Path):
    content = Path(input_md_file).read_text()

    # Convert to HTML
    parser = commonmark.Parser()
    renderer = commonmark.HtmlRenderer()
    ast = parser.parse(content)
    html = renderer.render(ast)

    # Add CSS
    css = """
  <style>
    body { max-width: 800px; margin: 40px auto; padding: 0 20px;
           font-family: -apple-system, system-ui, sans-serif; }
    pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; }
    code { font-family: 'SF Mono', Consolas, monospace; }
    .diff-block { background: #f8f9fa; padding: 10px; border-radius: 6px; margin: 10px 0; }
    .diff-add { color: #28a745; }
    .diff-remove { color: #cb2431; }
    .diff-context { color: #666; }
    h2 { border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
  </style>
  """

    toc = []
    for line in content.split("\n"):
        if line.startswith("## Chat History for"):
            path = line.replace("## Chat History for ", "").strip()
            name = path.split("/")[-1]
            toc.append(f'<a href="#{name}">{name}</a><br>')
            html = html.replace(
                f"<h2>Chat History for {path}</h2>",
                f'<h2 id="{name}">Chat History for {path}</h2>',
            )

    # Insert TOC at top
    toc_html = "<h2>Table of Contents</h2>\n" + "\n".join(toc) + "<hr>\n"
    html = toc_html + html

    output_html_file.write_text(
        f"<!DOCTYPE html><html><head>{css}</head><body>{html}</body></html>"
    )
    print(f"HTML version written to {output_html_file}")


def serve_html(base_dir):
    app = Flask(__name__)
    base_path = Path(base_dir)

    @app.route("/")
    def index():
        dirs = [d for d in base_path.iterdir() if d.is_dir()]

        # sort in date order
        dirs = sorted(dirs, key=lambda d: d.stat().st_ctime, reverse=True)

        links = [f'<a href="/process/{d.name}">{d.name}</a><br>' for d in dirs]
        return f"<h1>Select a directory to process:</h1>\n{''.join(links)}"

    @app.route("/process/<path:subdir>")
    def process_dir(subdir):
        full_path = base_path / subdir
        if not full_path.is_dir():
            return "Directory not found", 404

        output_md = full_path / "combined_chat_history.md"
        cleaned_md = full_path / "cleaned_chat_history.md"
        output_html = full_path / "combined_chat_history.html"
        output_html = output_html.resolve()

        collect_failed_histories(str(full_path), output_md)

        cleanup_md(output_md, cleaned_md)
        convert_to_html(cleaned_md, output_html)
        return send_file(output_html)

    print("Starting Flask server at http://localhost:9999")
    app.run(host="0.0.0.0", port=9999)


app = typer.Typer()


@app.command()
def main(
    base_dir: str = typer.Option(help="Base directory to search for failed tests"),
):
    """Browse directories and collect failed test chat histories"""
    serve_html(base_dir)


if __name__ == "__main__":
    app()
