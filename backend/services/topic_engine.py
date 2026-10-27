"""Topic engine - finds the real *concepts* in a lecture, transcript or document.

Old behaviour: cut the content into fixed-size windows and call each window by its single most frequent word.
New behaviour:
  1. A concept lexicon (variables, data types, loops, functions, OOP, SQL, React, finance, ...) is matched
     against every sentence, so a Python lecture becomes  Variables -> Data Types -> Conditionals -> Loops ->
     Functions ...  instead of "Python", "Code", "Thing".
  2. Content is split where the concept changes (with hysteresis so it doesn't flicker), tiny pieces are merged,
     huge ones are split into "definition", "example" and "going deeper" parts.
  3. If the lexicon doesn't recognise the subject (history, cooking, any niche), a TextTiling-style vocabulary
     shift detector finds the topic boundaries and a TF-IDF key-phrase extractor names them.
  4. Documents with headings (Markdown, Word headings, "1. Variables", "Chapter 2: ...") use the headings.

Pure Python, no extra dependencies, works offline.
"""
import bisect
import collections
import math
import re

# ====================================================================== concept lexicon
# "term^weight"  - weight defaults to 1.0 (single word) or 1.5 (phrase). Plurals (s / es) match automatically.
# Ambiguous words get low weights so they never decide a topic on their own.
LEXICON = {
    "Programming": {
        "Getting Started": "python^0.3, interpreter^2, code editor^2.5, integrated development environment^3.5, vs code^2.5, jupyter^2.5, install python^3.5, installation^2, "
                           "setup^1.5, indentation^2.5, comment^1.5, hello world^3.5, pep 8^3, first program^3, "
                           "run your code^2, python 3^1.5, syntax^1.2, what is programming^3, programming language^2",
        "Variables": "variable^2.2, assignment^1.5, assign^1, assigned^1, reassign^1.5, identifier^1, naming rule^2.5, "
                     "naming convention^2.5, snake case^2.5, camel case^2, constant^1, declare^1, memory location^1.5, "
                     "store a value^2.5, storing a value^2.5, variable name^2.5, multiple assignment^3",
        "Data Types": "data type^3, datatype^3, integer^1.5, int^0.7, float^1.5, floating point^2, boolean^1.5, bool^0.7, "
                      "nonetype^2, type casting^3, typecasting^3, type conversion^3, dynamic typing^3, static typing^2, "
                      "type()^2.5, isinstance^2, complex number^1.5, numeric type^2, primitive^1.5",
        "Strings": "string^1.5, f-string^3, slicing^1, concatenate^2, concatenation^2, upper()^2, lower()^2, strip()^1.5, "
                   "split()^2, join()^2, replace()^1, escape character^2.5, multiline string^2.5, string method^3, "
                   "string formatting^3, substring^2.5, character^1, len()^1.5",
        "Operators": "operator^2, arithmetic^1.5, modulus^2.5, modulo^2.5, floor division^3, exponent^1.5, "
                     "comparison operator^3, logical operator^3, assignment operator^3, membership operator^3, "
                     "identity operator^3, operator precedence^3, bitwise^2.5, increment^1.5, ==^1, !=^1",
        "Input and Output": "input()^3, user input^3, print()^2.5, print statement^2.5, console^1, format specifier^2.5, "
                            "stdin^2.5, stdout^2.5, take input^2.5, display output^2.5",
        "Conditionals": "conditional^2.5, if statement^3, elif^3, else if^2.5, else statement^2.5, if else^3, nested if^3, "
                        "decision making^2.5, ternary^3, condition^1, branching^1.5, boolean expression^2.5, truthy^2.5, "
                        "falsy^2.5, match case^3, switch case^2.5, control flow^2.5",
        "Loops": "loop^2.2, for loop^3.5, while loop^3.5, iterate^1.5, iteration^1.5, range()^3, break statement^3, "
                 "continue statement^3, infinite loop^3.5, nested loop^3.5, enumerate^2.5, loop variable^2.5, looping^2",
        "Lists": "list^1, append^2, insert()^1.5, pop()^2.5, remove()^1.5, extend()^2.5, list slicing^3, sort()^1.5, "
                 "sorted()^1.5, indexing^1.5, mutable^1.5, nested list^3, list method^3, 2d list^3, negative index^2.5",
        "Tuples and Sets": "tuple^3.5, immutable^1.5, set^0.5, union^1.5, intersection^1.5, unique elements^2.5, "
                           "frozenset^3, unpacking^2, duplicate^1, set operation^3",
        "Dictionaries": "dictionary^3.5, dict^2, key value^3.5, key-value^3.5, keys()^2.5, values()^2.5, items()^2.5, "
                        "hash map^2.5, get()^1, nested dictionary^3.5",
        "Functions": "function^2, def^2, return value^3, return statement^3, parameter^2, argument^1.5, default argument^3.5, "
                     "default parameter^3.5, keyword argument^3.5, positional argument^3.5, *args^3.5, **kwargs^3.5, "
                     "calling a function^3.5, call a function^3.5, define a function^3.5, built-in function^2.5, "
                     "docstring^2.5, void function^2.5, reusable code^2.5, reusability^2, return^0.8",
        "Lambda and Comprehensions": "lambda^3.5, anonymous function^3.5, list comprehension^4, dictionary comprehension^4, "
                                     "comprehension^3, map()^2.5, filter()^2.5, reduce()^2.5, higher-order function^3.5, "
                                     "generator^2.5, yield^3, decorator^3.5",
        "Scope": "scope^3, local variable^3.5, global variable^3.5, global keyword^3.5, nonlocal^3.5, legb^3.5, "
                 "enclosing scope^3.5, namespace^2.5",
        "Recursion": "recursion^4, recursive^3.5, base case^4, recursive call^4, call stack^3, factorial^1.5, fibonacci^2, "
                     "stack overflow^2.5, recursion depth^3.5",
        "Classes and OOP": "class^1.5, object^1, instance^1.5, method^1.5, self^1.5, __init__^3.5, init method^3.5, "
                           "constructor^3.5, attribute^1.5, encapsulation^3.5, inheritance^3.5, polymorphism^3.5, "
                           "abstraction^3, super()^3.5, subclass^3.5, superclass^3.5, parent class^3.5, child class^3.5, "
                           "dunder^3, overriding^3.5, oop^3.5, object oriented^3.5, object-oriented^3.5",
        "Exception Handling": "exception^2.5, try block^3.5, except block^3.5, try except^4, try-except^4, finally^1.5, "
                              "raise^1.5, raise an exception^3.5, error handling^4, traceback^2.5, valueerror^3.5, "
                              "typeerror^3.5, zerodivisionerror^3.5, custom exception^4, handling errors^3.5",
        "File Handling": "file handling^4, open()^2, with open^4, read()^1.5, readline^3, readlines^3, write()^1.5, "
                         "append mode^3, file mode^3, close()^1.5, text file^3, file path^3, context manager^3.5",
        "Modules and Libraries": "module^2, import^1.5, package^2, library^1.5, pip^2.5, pip install^3.5, standard library^3.5, "
                                 "third-party^2.5, math module^3.5, random module^3.5, datetime^2, virtual environment^3.5, venv^3.5",
        "Debugging": "debug^2.5, debugging^3.5, debugger^3.5, bug^2, breakpoint^3.5, syntax error^3.5, runtime error^3.5, "
                     "logic error^3.5, stack trace^3, print debugging^3.5, error message^2, logging^2",
        "Algorithms": "algorithm^2.5, big o^4, time complexity^4, space complexity^4, binary search^4, linear search^4, "
                      "bubble sort^4, merge sort^4, quick sort^4, sorting algorithm^4, divide and conquer^3.5, "
                      "dynamic programming^4, greedy^2",
        "Data Structures": "data structure^4, stack^2, queue^2.5, linked list^4, binary tree^4, tree^1, graph^1.5, "
                           "hash table^3.5, heap^2.5, array^1.5, deque^3.5, priority queue^4",
    },
    "Web Development": {
        "HTML": "html^3, tag^1, element^1, div^2, semantic html^4, heading tag^3, anchor tag^3.5, doctype^3.5, "
                "html form^3, input field^2",
        "CSS": "css^3, selector^2.5, flexbox^4, grid^1.5, margin^2, padding^2, box model^4, class selector^3.5, "
               "media query^4, responsive^2, stylesheet^3, font^1",
        "JavaScript": "javascript^2, dom^3, event listener^3.5, addeventlistener^4, arrow function^3.5, promise^3, "
                      "async^2.5, await^2.5, callback^3, const^2, var^1, fetch^2, closure^3.5, hoisting^3.5, template literal^3",
        "React": "react^3, component^2.5, props^3.5, usestate^4, useeffect^4, hook^2, jsx^4, virtual dom^4, render^1.5, "
                 "redux^3, context api^3",
        "APIs": "api^2.5, rest^0.4, restful^3, endpoint^3, http^2.5, get request^3, post request^3, status code^3, "
                "response^1.5, authentication^2, fastapi^3, flask^3, django^3, backend^1.5",
    },
    "Databases": {
        "SQL Queries": "sql^3, select statement^3.5, where clause^3.5, insert into^3.5, query^2, database^1.5, "
                       "order by^3, group by^3.5, aggregate^2.5, table^1, row^1, column^1, nosql^3, mongodb^3, "
                       "postgres^3, mysql^3, sqlite^3",
        "Joins": "join^2.5, inner join^4, left join^4, right join^4, outer join^4, join table^3.5",
        "Keys and Constraints": "primary key^4, foreign key^4, unique constraint^3.5, normalization^4, constraint^2, "
                                "relationship^1.5, schema^2.5, index^1",
    },
    "Version Control": {
        "Git and Version Control": "git^3, commit^3, repository^2.5, repo^2, clone^3, branch^2.5, merge^3, pull request^4, "
                                   "push^2, staging area^4, git add^4, git commit^4, merge conflict^4, rebase^4, github^3, "
                                   "gitignore^4, checkout^3, version control^4",
    },
    "Data Science": {
        "Machine Learning": "machine learning^4, model^1.2, training^2, dataset^2.5, data set^2.5, feature^1.5, label^1, "
                            "supervised^3, unsupervised^3, overfitting^4, underfitting^4, accuracy^2, regression^3, "
                            "classification^3, neural network^4, deep learning^4, gradient descent^4, scikit-learn^3, "
                            "sklearn^3, test set^3, train test split^4",
        "Data Analysis": "pandas^3, dataframe^4, numpy^3, matplotlib^3, visualization^2, chart^1.5, data cleaning^4, "
                         "missing value^3, mean^1, median^1.5, correlation^2.5, seaborn^3",
    },
    "Marketing": {
        "Marketing and Growth": "marketing^2.5, audience^2, brand^2, branding^2.5, conversion^3, funnel^3, seo^3, "
                                "content strategy^4, engagement^2.5, campaign^2.5, target audience^3.5, social media^2, "
                                "influencer^2.5, lead generation^4, call to action^3",
    },
    "Finance": {
        "Money and Investing": "investing^2.5, investment^2, stock^2, mutual fund^4, interest rate^3, inflation^3, budget^2, "
                               "savings^2, compound interest^4, portfolio^3, diversification^4, risk^1.5, sip^3, loan^2, "
                               "credit score^4",
    },
    "Health": {
        "Fitness and Nutrition": "workout^2.5, exercise^1.5, protein^2.5, calories^2.5, nutrition^2.5, diet^2, cardio^3, "
                                 "strength training^4, sleep^1.5, hydration^3, muscle^2, metabolism^3, stretching^3",
    },
    "Mathematics": {
        "Math Concepts": "equation^2.5, algebra^4, geometry^4, calculus^4, derivative^3, integral^3, probability^3, "
                         "statistics^2.5, theorem^3, fraction^2.5, polynomial^4, matrix^3, vector^2",
    },
}

DOMAIN_TAGS = {
    "Programming": ["#coding", "#programming", "#learntocode"],
    "Web Development": ["#webdev", "#frontend"],
    "Databases": ["#sql", "#database"],
    "Version Control": ["#git", "#github"],
    "Data Science": ["#datascience", "#machinelearning"],
    "Marketing": ["#marketing", "#growth"],
    "Finance": ["#finance", "#investing"],
    "Health": ["#fitness", "#health"],
    "Mathematics": ["#maths", "#learnmaths"],
}
LANGUAGES = {"python": "Python", "javascript": "JavaScript", "java": "Java", "typescript": "TypeScript",
             "c++": "C++", "c#": "C#", "golang": "Go", "rust": "Rust", "php": "PHP", "kotlin": "Kotlin"}


def _compile():
    out = {}
    for domain, concepts in LEXICON.items():
        for name, spec in concepts.items():
            seen, plist = set(), []
            for part in spec.split(","):
                part = part.strip()
                if not part:
                    continue
                term, _, w = part.partition("^")
                term = term.strip().lower()
                if term in seen:
                    continue
                seen.add(term)
                weight = float(w) if w else (1.5 if " " in term else 1.0)
                body = re.escape(term).replace(r"\ ", r"[\s\-]+")
                rx = re.compile(r"(?<![a-z0-9_])" + body + r"(?:s|es)?(?![a-z0-9_])")
                plist.append((rx, weight, term))
            out[name] = (domain, plist)
    return out


COMPILED = _compile()
MIN_HIT = 1.5            # smoothed score a concept needs before it can own a stretch of content

# ====================================================================== language helpers
STOP = set("""a about above after again all also am an and any are as at be because been before being below between both
but by can could did do does doing down during each few for from further get got had has have having he her here hers him
his how i if in into is it its just let like me more most my no nor not now of off on once only or other our out over own
really same she should so some such than that the their them then there these they this those through to too under until up
very was we were what when where which while who why will with would you your yeah okay ok um uh going gonna want need
today next first second thing things one two three say said see look know right well make use used using actually basically
simply kind sort stuff lot bit guys everyone welcome hello hi thanks thank""".split())

FILLER = set("""example examples video lecture tutorial course lesson time way part able start end new good great better best
important different common simple easy hard small big long little many much back something anything everything someone nothing
point case works work called mean means code program run write written create created type types value values result results
number numbers line lines name names called inside outside basic basics concept concepts topic topics print let lets sure scratch ten writing set""".split())

DEF_CUES = re.compile(r"\b(is a|is an|are a|are the|is called|are called|is known as|means|refers to|stands for|"
                      r"defined as|definition|let's define|what is|what are|in simple words|in other words|"
                      r"you can think of|think of it as)\b", re.I)
EX_CUES = re.compile(r"\b(for example|for instance|example|let's see|let us see|let's try|let's write|let's run|"
                     r"the output|output (?:is|will|shows)|as you can see|demo|suppose|say we|e\.g|here we|try this|run this)\b", re.I)

TITLE_T = {
    "definition": ["{X} Explained", "Understanding {X}", "{X} in Simple Words"],
    "example": ["{X} Example: See It in Action", "{X}: A Worked Example", "{X} in Action"],
    "overview": ["{X} Made Easy", "Quick Guide to {X}", "{X}: What You Need to Know"],
    "continued": ["More on {X}", "{X}: Going Deeper", "{X} Tips and Tricks"],
}
HOOKS = {
    "definition": "Still confused about {x}? Here's the simple version.",
    "example": "Don't just read about {x} - watch it work.",
    "overview": "Everything you need to know about {x}, fast.",
    "continued": "Ready to level up your {x}?",
}
CAPTIONS = {
    "educational": "A quick, clear explanation of {t}. Save this for revision! 📚",
    "genz": "{t}, but make it make sense ✨ no cap, this one's a lifesaver",
    "professional": "A concise breakdown of {t} - practical insights you can apply today.",
    "funny": "POV: you finally understand {t} 😭☕",
}


# ====================================================================== small utilities
def _words(text: str) -> int:
    return len(text.split())


def _norm(tok: str) -> str:
    if tok.endswith("ies") and len(tok) > 4:
        return tok[:-3] + "y"
    if tok.endswith("s") and not tok.endswith("ss") and len(tok) > 3:
        return tok[:-1]
    return tok


def _cos(a: collections.Counter, b: collections.Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _tag(s: str) -> str:
    parts = re.findall(r"[A-Za-z0-9+#]+", s)
    return "#" + "".join(p[:1].upper() + p[1:] for p in parts) if parts else ""


def _title_case(s: str) -> str:
    small = {"a", "an", "the", "of", "and", "or", "in", "on", "to", "for", "vs", "with"}
    ws = s.split()
    return " ".join(w if (i and w.lower() in small) else (w[:1].upper() + w[1:]) for i, w in enumerate(ws))


def _sentences(text: str) -> list[str]:
    out = []
    for line in re.split(r"\n+", text):
        line = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s+", "", line).strip()
        if not line:
            continue
        out += [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
    return out


# ====================================================================== document parsing (headings)
_HEAD_MD = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
_HEAD_LABELLED = re.compile(r"^(?:chapter|section|unit|lesson|module|part|topic)\s+\d+\s*[:.\-\u2013]?\s*(.{2,70})$", re.I)
_HEAD_NUMBERED = re.compile(r"^\d+(?:\.\d+)*[.)]?\s+([A-Z][^\n]{2,70})$")


def _clean_heading(h: str) -> str:
    h = re.sub(r"^\s*(?:\d+(?:\.\d+)*[.)]?|chapter\s+\d+|section\s+\d+|unit\s+\d+|lesson\s+\d+)\s*[:.\-\u2013]?\s*", "", h, flags=re.I)
    h = h.strip().strip(":").strip("*_ ")
    if h.isupper() and len(h) > 3:
        h = h.title()
    return _title_case(h) if h else h


def _heading_of(line: str, nxt: str | None) -> str | None:
    s = line.strip()
    if not s or len(s) > 90:
        return None
    m = _HEAD_MD.match(s)
    if m:
        return _clean_heading(m.group(1))
    if s[-1:] in ".,;!?" or s.startswith(("-", "*", "\u2022")):
        return None
    m = _HEAD_LABELLED.match(s) or (_HEAD_NUMBERED.match(s) if len(s.split()) <= 10 else None)
    if m and nxt:
        return _clean_heading(m.group(1))
    ws = s.rstrip(":").split()
    if 1 <= len(ws) <= 9 and nxt and _words(nxt) >= 10:
        caps = sum(1 for w in ws if w[:1].isupper()) / len(ws)
        if s.isupper() or caps >= 0.6 or s.endswith(":"):
            return _clean_heading(s)
    return None


def _parse_doc(text: str):
    """-> (sentence units each tagged with a section index, sections [{heading}]). Sections only when headings exist."""
    lines = text.splitlines()
    sections = [{"heading": None}]
    units, para = [], 0
    for i, line in enumerate(lines):
        if not line.strip():
            para += 1
            continue
        nxt = next((l for l in lines[i + 1:i + 3] if l.strip()), None)
        h = _heading_of(line, nxt)
        if h:
            sections.append({"heading": h})
            continue
        for s in _sentences(line):
            units.append({"text": s, "start": None, "end": None, "sec": len(sections) - 1, "para": para})
    return units, sections


# ====================================================================== lexicon scoring
def _score_units(units):
    scores, terms = [], []
    for u in units:
        t = u["text"].lower()
        sc, tm = collections.Counter(), collections.defaultdict(collections.Counter)
        for cname, (_dom, plist) in COMPILED.items():
            for rx, w, canon in plist:
                k = len(rx.findall(t))
                if k:
                    v = w * (1 + math.log(k))
                    sc[cname] += v
                    tm[cname][canon] += v
        scores.append(sc)
        terms.append(tm)
    dom_tot = collections.Counter()
    for sc in scores:
        for c, v in sc.items():
            dom_tot[COMPILED[c][0]] += v
    main = dom_tot.most_common(1)[0][0] if dom_tot else None
    for sc in scores:                                   # concepts outside the main subject count a bit less
        for c in list(sc):
            if COMPILED[c][0] != main:
                sc[c] *= 0.6
    return scores, terms, main


def _label_units(scores):
    n = len(scores)
    smooth = []
    for i in range(n):
        s = collections.Counter()
        for j in range(max(0, i - 2), min(n, i + 3)):
            w = 1 - 0.25 * abs(i - j)
            for c, v in scores[j].items():
                s[c] += v * w
        smooth.append(s)
    labels, cur = [], None
    for i in range(n):
        if smooth[i]:
            best, bv = smooth[i].most_common(1)[0]
            if cur is None:
                cur = best if bv >= MIN_HIT else None
            elif best != cur and bv >= max(MIN_HIT, 1.3 * smooth[i].get(cur, 0)):
                cur = best
        labels.append(cur)
    # snap each change to the sentence that actually announces the new concept
    for b in range(1, n):
        if labels[b] != labels[b - 1] and labels[b] is not None:
            new = labels[b]
            k = next((k for k in range(max(0, b - 3), min(n, b + 3)) if scores[k].get(new, 0) >= 1.0), None)
            if k is not None and k < b:
                for x in range(k, b):
                    labels[x] = new
            elif k is not None and k > b:
                for x in range(b, k):
                    labels[x] = labels[b - 1]
    first = next((l for l in labels if l), None)         # back-fill an unlabeled intro
    return [l or first for l in labels]


# ====================================================================== block building
def _split_block(i0, i1, mn, mx, bsize):
    total = bsize(i0, i1)
    if total <= mx or i1 - i0 < 2:
        return [(i0, i1)]
    k = max(1, math.ceil(total / mx))
    if k > 1 and total / k < mn:
        k -= 1
    out, start = [], i0
    for part in range(1, k):
        target = total / k
        best = min(range(start + 1, i1), key=lambda j: abs(bsize(start, j) - target))
        out.append((start, best))
        start = best
    out.append((start, i1))
    return [o for o in out if o[1] > o[0]]


def _concept_blocks(labels, scores, bsize, mn, mx):
    n = len(labels)
    blocks, s = [], 0
    for i in range(1, n + 1):
        if i == n or labels[i] != labels[s]:
            blocks.append([s, i, labels[s]])
            s = i

    def dom(i0, i1):
        c = collections.Counter()
        for i in range(i0, i1):
            c.update(scores[i])
        return c.most_common(1)[0][0] if c else None

    while len(blocks) > 1:
        k = next((k for k, b in enumerate(blocks) if bsize(b[0], b[1]) < mn), None)
        if k is None:
            break
        cand = [j for j in (k - 1, k + 1) if 0 <= j < len(blocks)]
        pick = max(cand, key=lambda j: (blocks[j][2] == blocks[k][2], bsize(blocks[j][0], blocks[j][1])))
        lo, hi = sorted((k, pick))
        new = [blocks[lo][0], blocks[hi][1], None]
        new[2] = dom(new[0], new[1]) or blocks[pick][2]
        blocks[lo:hi + 1] = [new]
    merged = []
    for b in blocks:                                    # coalesce neighbours that ended up with the same concept
        if merged and merged[-1][2] == b[2]:
            merged[-1][1] = b[1]
        else:
            merged.append(list(b))
    out = []
    for i0, i1, lab in merged:
        for a, b in _split_block(i0, i1, mn, mx, bsize):
            out.append({"i0": a, "i1": b, "concept": lab, "heading": None})
    return out


def _generic_blocks(units, bsize, mn, mx, para_only=False):
    n = len(units)
    vecs = []
    for u in units:
        c = collections.Counter()
        for _run in _runs(u["text"]):
            for t in _run:
                c[_norm(t)] += 1
        vecs.append(c)
    w = 4
    sims = {}
    for i in range(1, n):
        left, right = collections.Counter(), collections.Counter()
        for v in vecs[max(0, i - w):i]:
            left.update(v)
        for v in vecs[i:i + w]:
            right.update(v)
        sims[i] = _cos(left, right)
    bounds = [0, n]
    if sims:
        vals = list(sims.values())
        mean = sum(vals) / len(vals)
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        thresh = mean - 0.2 * std
        allowed = {i for i in sims if units[i].get("para") != units[i - 1].get("para")} if para_only else None
        for i in sorted(sims, key=lambda x: sims[x]):
            if allowed is not None:
                if i not in allowed:
                    continue
            elif sims[i] > thresh:
                break
            pos = bisect.bisect(bounds, i)
            left, right = bounds[pos - 1], bounds[pos]
            if i != left and i != right and bsize(left, i) >= mn and bsize(i, right) >= mn:
                bisect.insort(bounds, i)
    out = []
    for a, b in zip(bounds, bounds[1:]):
        for x, y in _split_block(a, b, mn, mx, bsize):
            out.append({"i0": x, "i1": y, "concept": None, "heading": None})
    return out


def _heading_blocks(units, sections, bsize, mn, mx):
    by_sec = collections.defaultdict(list)
    for i, u in enumerate(units):
        by_sec[u["sec"]].append(i)
    out = []
    for sid, idx in sorted(by_sec.items()):
        i0, i1 = idx[0], idx[-1] + 1
        h = sections[sid]["heading"]
        if bsize(i0, i1) < 15 and out:             # a heading with a one-line body: fold into the previous topic
            out[-1]["i1"] = i1
            continue
        for a, b in _split_block(i0, i1, mn, mx, bsize):
            out.append({"i0": a, "i1": b, "concept": None, "heading": h})
    return out


# ====================================================================== key-phrases (TF-IDF)
def _runs(text: str, with_case: bool = False):
    """Runs of consecutive content words (split at punctuation and stop-words)."""
    for sent in re.split(r"[.!?;:,\n()]+", text):
        run = []
        for idx, m in enumerate(re.finditer(r"[A-Za-z][A-Za-z0-9_+#'\-]*", sent)):
            raw = m.group(0).strip("'-")
            tok = raw.lower()
            if len(tok) < 3 or tok in STOP or "'" in tok:
                if run:
                    yield run
                run = []
            else:
                run.append((tok, idx > 0 and raw[:1].isupper()) if with_case else tok)
        if run:
            yield run


def _verbish(tok: str) -> bool:
    return (tok.endswith("ed") and len(tok) > 4) or (tok.endswith("ing") and len(tok) > 5) or tok in {
        "grew", "rose", "led", "took", "came", "went", "made", "became", "gave", "found", "held", "kept"}


def _phrase_counter(text: str):
    cnt, caps = collections.Counter(), collections.Counter()
    disp = collections.defaultdict(collections.Counter)
    for run in _runs(text, with_case=True):
        for i, (t, cap) in enumerate(run):
            if t in FILLER:
                continue
            k = _norm(t)
            cnt[k] += 1
            caps[k] += cap
            disp[k][t] += 1
            if i + 1 < len(run) and run[i + 1][0] not in FILLER:
                t2, cap2 = run[i + 1]
                k2 = f"{k} {_norm(t2)}"
                cnt[k2] += 1
                caps[k2] += (cap and cap2)
                disp[k2][f"{t} {t2}"] += 1
    return cnt, disp, caps


def _top_phrases(cnt, disp, df, nblocks, words, k=5, caps=None):
    scored = []
    for key, tf in cnt.items():
        parts = key.split()
        proper = bool(caps) and caps.get(key, 0) >= max(1, tf * 0.6)
        if len(parts) > 1 and tf < 2 and not proper:      # one-off bigrams are mostly noise ("senate advised")
            continue
        if tf < 2 and words > 90 and not proper:
            continue
        if any(_verbish(x) for x in parts):
            tf = tf * 0.4
        idf = math.log(1 + nblocks / max(1, df.get(key, 1)))
        score = tf * idf * (1.6 if len(parts) > 1 else 1.0) * (1.8 if proper else 1.0)
        scored.append((score, key))
    scored.sort(reverse=True)
    chosen = []
    for _s, key in scored:
        parts = set(key.split())
        if " " not in key and any(parts & set(c.split()) for c in chosen if " " in c):
            continue
        if " " in key:
            chosen = [c for c in chosen if not (" " not in c and c in parts)]
        chosen.append(key)
        if len(chosen) >= k:
            break
    return [disp[c].most_common(1)[0][0] for c in chosen]


# ====================================================================== topic assembly
def _key_points(sents: list[str], concept_terms: list[str], n: int = 3) -> list[str]:
    scored = []
    for i, s in enumerate(sents):
        s = re.sub(r"^(so|okay|ok|now|alright|and|well|um|uh)[,\s]+", "", s.strip(), flags=re.I)
        if not (30 <= len(s) <= 200):
            continue
        low = s.lower()
        sc = sum(2 for t in concept_terms if t in low)
        sc += 1.5 if DEF_CUES.search(s) else 0
        sc += 1.0 if EX_CUES.search(s) else 0
        sc += 0.5 if 50 <= len(s) <= 140 else 0
        scored.append((sc, i, s[:1].upper() + s[1:]))
    top = sorted(scored, key=lambda x: -x[0])[:n]
    return [s for _sc, _i, s in sorted(top, key=lambda x: x[1])]


def _dom_concept(sc: collections.Counter):
    return sc.most_common(1)[0] if sc else (None, 0.0)


def _make_topics(blocks, units, scores, terms, timed, opts, lang, main_domain, mode_concept=True):
    texts = [" ".join(units[i]["text"] for i in range(b["i0"], b["i1"])) for b in blocks]
    counters = [_phrase_counter(t) for t in texts]
    df = collections.Counter()
    for cnt, _d, _c in counters:
        df.update(cnt.keys())
    tone = opts.get("tone", "educational")
    seen, title_use, topics = collections.Counter(), collections.Counter(), []

    for bi, b in enumerate(blocks):
        text, (cnt, disp, caps) = texts[bi], counters[bi]
        sc, tm = collections.Counter(), collections.defaultdict(collections.Counter)
        for i in range(b["i0"], b["i1"]):
            sc.update(scores[i])
            for c, t in terms[i].items():
                tm[c].update(t)
        strict = 3.0 if (b["heading"] or not mode_concept) else MIN_HIT
        concept = b["concept"] or (_dom_concept(sc)[0] if _dom_concept(sc)[1] >= strict else None)
        words = _words(text)
        phrases = _top_phrases(cnt, disp, df, len(blocks), words, k=6, caps=caps)

        if b["heading"]:
            label = b["heading"]
        elif concept:
            label = concept
        else:
            label = _title_case(phrases[0]) if phrases else f"Key Idea {bi + 1}"

        d_cues, e_cues = len(DEF_CUES.findall(text)), len(EX_CUES.findall(text))
        first_time = seen[label] == 0
        if first_time and d_cues >= 1 and e_cues < 3 * d_cues + 2:
            kind = "definition"
        elif e_cues >= 2 and e_cues >= d_cues:
            kind = "example"
        else:
            kind = "definition" if d_cues >= 1 else "overview"
        if not first_time and kind == "overview":
            kind = "continued"
        seen[label] += 1

        # ---- keywords: concept terms first (these are what the topic is *about*), then distinctive phrases
        kws = []
        if concept:
            for canon, _v in tm[concept].most_common(4):
                kws.append(re.sub(r"\(\)$", "", canon).replace("-", " ") if not canon.startswith("__") else canon)
        need = 6 if not concept else (5 if len(kws) < 2 else 0)
        for p in phrases:
            if len(kws) >= need:
                break
            key = _norm(p.split()[-1]) if " " not in p else None
            if concept and cnt.get(_norm(p) if " " not in p else " ".join(_norm(x) for x in p.split()), 0) < 2:
                continue
            if not any(p in k or k in p for k in kws) and p.lower() != label.lower():
                kws.append(p)
        kws = list(dict.fromkeys(k.lower() for k in kws))[:6]

        # ---- titles / hook / caption
        if b["heading"]:
            title = label if first_time else f"More on {label}"
        else:
            X = label
            if lang and concept and COMPILED[concept][0] == "Programming" and lang.lower() not in X.lower() \
                    and concept != "Getting Started":
                X = f"{lang} {label}"
            variants = TITLE_T[kind]
            title = variants[title_use[(label, kind)] % len(variants)].format(X=X)
            title_use[(label, kind)] += 1
        topic_name = f"{label} - example" if kind == "example" and not b["heading"] else label
        x = label.lower()
        caption = CAPTIONS.get(tone, CAPTIONS["educational"]).format(t=label)
        if kws:
            caption += f" Covers: {', '.join(kws[:3])}."

        # ---- hashtags
        tags = [_tag(label)]
        if lang:
            tags.append(_tag(lang))
        tags += [_tag(k) for k in kws[:4]]
        if concept:
            tags += DOMAIN_TAGS.get(COMPILED[concept][0], [])
        uniq, seen_tags = [], set()
        for t in tags:
            k = _norm(t.lower())
            if len(t) > 2 and k not in seen_tags:
                seen_tags.add(k)
                uniq.append(t)
        tags = uniq[:10]

        # ---- importance
        pc, pv = (concept, sc.get(concept, 0.0)) if concept else (None, 0.0)
        strength = min(1.0, (pv * 100 / max(words, 20)) / 15) if pc else min(1.0, len(phrases) / 6)
        imp = 0.40 + 0.28 * strength + (0.12 if kind == "definition" else 0.08 if kind == "example" else 0) \
            + (0.08 if first_time else -0.10)
        if seen[label] > 2:
            imp *= 0.9
        if concept == "Getting Started":
            imp -= 0.2

        sents = _sentences(text)
        topics.append({
            "topic": topic_name, "title": title,
            "hook": HOOKS[kind].format(x=x),
            "caption": caption, "hashtags": tags, "keywords": kws,
            "key_points": _key_points(sents, [k for k in kws[:4]]) or [s[:160] for s in sents[:2]],
            "importance": round(max(0.30, min(0.98, imp)), 2),
            "start": units[b["i0"]]["start"] if timed else None,
            "end": units[b["i1"] - 1]["end"] if timed else None,
            "_concept": concept, "_kind": kind, "_label": label,
        })
    return topics


# ====================================================================== public API
def analyze(units: list[dict], opts: dict, timed: bool, text: str | None = None) -> dict:
    sections = None
    if not timed and text:
        units, sections = _parse_doc(text)
        if len([s for s in sections if s["heading"]]) < 2:
            sections = None
    units = [u for u in units if (u.get("text") or "").strip()]
    if not units:
        return {"summary": "", "keywords": [], "topics": [], "provider": "heuristic", "warning": None}

    if timed:
        mn, mx = float(opts["min_clip_seconds"]), float(max(opts["max_clip_seconds"], opts["min_clip_seconds"] + 5))

        def bsize(a, b):
            return units[b - 1]["end"] - units[a]["start"]
    else:
        mn, mx = 30.0, 200.0
        prefix = [0]
        for u in units:
            prefix.append(prefix[-1] + _words(u["text"]))

        def bsize(a, b):
            return prefix[b] - prefix[a]

    scores, terms, main_domain = _score_units(units)
    coverage = sum(1 for s in scores if sum(s.values()) >= 1.0) / len(units)
    full = " ".join(u["text"] for u in units)
    low = full.lower()
    lang_hits = {name: len(re.findall(r"(?<![a-z0-9_])" + re.escape(k) + r"(?![a-z0-9_+#])", low))
                 for k, name in LANGUAGES.items()}
    lang = max(lang_hits, key=lang_hits.get) if lang_hits and max(lang_hits.values()) >= 3 else None

    if sections:
        blocks = _heading_blocks(units, sections, bsize, mn, mx)
    elif coverage >= 0.30:
        blocks = _concept_blocks(_label_units(scores), scores, bsize, mn, mx)
    else:
        blocks = _generic_blocks(units, bsize, mn, mx, para_only=not timed and "para" in units[0])
    if not blocks:
        blocks = [{"i0": 0, "i1": len(units), "concept": None, "heading": None}]

    topics = _make_topics(blocks, units, scores, terms, timed, opts, lang, main_domain,
                          mode_concept=(not sections and coverage >= 0.30))

    order = []
    for t in topics:
        name = t["_label"]
        if name not in order:
            order.append(name)
    keywords = ([lang] if lang else []) + order
    if len(order) < 3:                                     # no clear concepts: use the strongest content phrases
        cnt, disp, caps = _phrase_counter(full)
        keywords += [p for p in _top_phrases(cnt, disp, {}, 1, 999, k=8, caps=caps) if p.lower() not in [k.lower() for k in keywords]]
    keywords = keywords[:12]

    shown = order[:6]
    covers = shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]
    kind_word = "video" if timed else "document"
    lang_word = f"{lang} " if lang and main_domain == "Programming" else ""
    summary = f"This {lang_word}{kind_word} covers {covers}." if order else ""
    first = next((s for s in _sentences(full) if len(s) > 40), "")
    if first:
        summary = (summary + " " + first[:200]).strip()

    return {"summary": summary, "keywords": keywords, "topics": topics, "provider": "heuristic", "warning": None}


def suggest_keywords(text: str, k: int = 6) -> list[str]:
    """Topic-specific keywords for one chunk of text (used to fill gaps in LLM output)."""
    r = analyze([{"start": 0.0, "end": 1.0, "text": text}], {"min_clip_seconds": 1, "max_clip_seconds": 10 ** 6,
                                                              "tone": "educational"}, timed=True)
    return (r["topics"][0]["keywords"] if r["topics"] else [])[:k]
