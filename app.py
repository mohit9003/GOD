from flask import Flask, render_template, request, send_file, jsonify
import ast, re, io, subprocess, tempfile, os, sys

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

# -------------------------------------------------
# LANGUAGE DETECTION
# -------------------------------------------------
def detect_language(code):
    c = code.lower()
    if "public static void main" in c:
        return "java"
    if "#include" in c and ("printf" in c or "scanf" in c):
        return "c"
    if "#include" in c and ("cout" in c or "cin" in c):
        return "cpp"
    return "python"

# -------------------------------------------------
# SECURITY (LIVE SAFE)
# -------------------------------------------------
FORBIDDEN = [
    "import os",
    "import sys",
    "import subprocess",
    "open(",
    "while true",
    "__import__",
    "fork"
]

def is_safe_python(code):
    lower = code.lower()
    for bad in FORBIDDEN:
        if bad in lower:
            return False, bad
    return True, None

# -------------------------------------------------
# HELPERS FOR FLOWCHART LABELS
# -------------------------------------------------
def extract_assignment(line):
    return line.split("=")[0].strip()

def extract_condition(line):
    return (
        line.replace("if", "")
            .replace("(", "")
            .replace(")", "")
            .replace(":", "")
            .strip()
    )

def extract_loop(line):
    if "for" in line:
        return line[line.find("for")+3:].replace(":", "").strip()
    if "while" in line:
        return line.replace("while", "").replace(":", "").strip()
    return "Loop"

# -------------------------------------------------
# FLOWCHART
# -------------------------------------------------
def generate_flowchart(code, lang):
    has_if = bool(re.search(r"\bif\b", code))
    has_loop = bool(re.search(r"\bfor\b|\bwhile\b", code))

    diagram = [
        "flowchart TD",
        "classDef start fill:#f6b26b,color:#000;",
        "classDef process fill:#8e9aff,color:#000;",
        "classDef decision fill:#ff7edb,color:#000;"
    ]

    lines = [l.strip() for l in code.split("\n") if l.strip()]

    if not has_if and not has_loop:
        var = extract_assignment(lines[0]) if lines else "Data"
        diagram += [
            "S([Start]):::start",
            f'P["Set {var}"]:::process',
            "E([End]):::start",
            "S --> P --> E"
        ]
        return "\n".join(diagram)

    if has_if and not has_loop:
        cond = extract_condition(next(l for l in lines if l.startswith("if")))
        diagram += [
            "S([Start]):::start",
            f'D{{{cond}}}:::decision',
            'T["True Block"]:::process',
            'F["False Block"]:::process',
            "E([End]):::start",
            "S --> D",
            "D -->|Yes| T --> E",
            "D -->|No| F --> E"
        ]
        return "\n".join(diagram)

    if has_loop and not has_if:
        loop = extract_loop(next(l for l in lines if l.startswith(("for","while"))))
        diagram += [
            "S([Start]):::start",
            f'D{{{loop}}}:::decision',
            'B["Loop Body"]:::process',
            "E([End]):::start",
            "S --> D",
            "D -->|Repeat| B --> D",
            "D -->|Exit| E"
        ]
        return "\n".join(diagram)

    cond = extract_condition(next(l for l in lines if l.startswith("if")))
    loop = extract_loop(next(l for l in lines if l.startswith(("for","while"))))

    diagram += [
        "S([Start]):::start",
        f'D{{{cond}}}:::decision',
        f'L{{{loop}}}:::decision',
        'B["Process Block"]:::process',
        "E([End]):::start",
        "S --> D",
        "D -->|Yes| L",
        "D -->|No| E",
        "L -->|Repeat| B --> L",
        "L -->|Exit| E"
    ]

    return "\n".join(diagram)

# -------------------------------------------------
# ALGORITHM
# -------------------------------------------------
def generate_algorithm(code):
    steps = ["1. Start the program."]
    step = 2

    for line in code.split("\n"):
        l = line.strip()
        if not l:
            continue

        if "=" in l and not l.startswith(("if", "for", "while")):
            steps.append(f"{step}. Assign values to variables.")
        elif l.startswith("if"):
            steps.append(f"{step}. Check the condition.")
        elif l.startswith(("for", "while")):
            steps.append(f"{step}. Execute loop.")
        elif "print" in l:
            steps.append(f"{step}. Display output.")
        step += 1

    steps.append(f"{step}. Stop the program.")
    return "\n".join(steps)

# -------------------------------------------------
# EXPLANATION
# -------------------------------------------------
def explain_code(code):
    explanation = []
    ln = 1
    for line in code.split("\n"):
        l = line.strip()
        if not l:
            ln += 1
            continue

        if "=" in l:
            explanation.append(f"Line {ln}: Variable assignment.")
        elif l.startswith("if"):
            explanation.append(f"Line {ln}: Condition checking.")
        elif l.startswith(("for","while")):
            explanation.append(f"Line {ln}: Loop execution.")
        elif "print" in l:
            explanation.append(f"Line {ln}: Output statement.")
        else:
            explanation.append(f"Line {ln}: Statement execution.")
        ln += 1

    return "\n".join(explanation)

# -------------------------------------------------
# COMPLEXITY
# -------------------------------------------------
def time_complexity(code):
    loops = len(re.findall(r"\bfor\b|\bwhile\b", code))
    return "O(1)" if loops == 0 else "O(n)" if loops == 1 else "O(n²)"

def space_complexity(code):
    return "O(1)"

def cyclomatic_complexity(code):
    d = len(re.findall(r"\bif\b|\bfor\b|\bwhile\b", code))
    return f"Cyclomatic Complexity = {d + 1}"

def extra_metrics(code):
    return {
        "decisions": len(re.findall(r"\bif\b", code)),
        "loops": len(re.findall(r"\bfor\b|\bwhile\b", code)),
        "paths": len(re.findall(r"\bif\b", code)) + 1,
        "risk": "Low"
    }

def auto_summary(code):
    return "Static analysis with optional safe Python execution."

# -------------------------------------------------
# SAFE PYTHON RUNNER (LIVE)
# -------------------------------------------------
def run_python_code(code):
    safe, bad = is_safe_python(code)
    if not safe:
        return {"error": f"Blocked for security: {bad}"}

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            fname = f.name

        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True,
            text=True,
            timeout=3
        )

        if result.stderr:
            return {"error": result.stderr}

        return {"output": result.stdout or "No Output"}

    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out."}

    finally:
        if os.path.exists(fname):
            os.remove(fname)

# -------------------------------------------------
# ROUTES
# -------------------------------------------------
@app.route("/", methods=["GET","POST"])
def index():
    if request.method == "POST":
        code = request.form["code"]
        lang = detect_language(code)
        metrics = extra_metrics(code)

        return render_template(
            "index.html",
            flowchart=generate_flowchart(code, lang),
            algorithm=generate_algorithm(code),
            explanation=explain_code(code),
            time=time_complexity(code),
            space=space_complexity(code),
            cyclomatic=cyclomatic_complexity(code),
            metrics=metrics,
            summary=auto_summary(code),
            lang=lang.upper()
        )
    return render_template("index.html")

@app.route("/run_code", methods=["POST"])
def run_code():
    code = request.form["code"]
    if detect_language(code) != "python":
        return jsonify({"error": "Only Python execution supported in live mode."})
    return jsonify(run_python_code(code))

# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
