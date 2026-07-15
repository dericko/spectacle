import re

# Manim's MathTex() compiles this text via a LaTeX subprocess, and sympy's
# sympify() evaluates it via Python's eval() under the hood — both are
# code-execution/code-compilation sinks. Scenes only ever need numeric
# arithmetic, so reject anything outside that character set before either
# sink sees it. This check must run independent of the pedagogical `verify`
# flag: `verify` gates whether we *check the math is correct*, not whether
# the text is *safe to hand to LaTeX/eval*.
SAFE_EXPRESSION_RE = re.compile(r"^[0-9+\-*/().\s%^]+$")

# The script agent writes render_params["steps"][i]["expr"] as LaTeX so
# Manim's MathTex can render proper stacked fractions (e.g.
# r"\frac{3}{4} + \frac{1}{8}"). This is a fixed, structural whitelist of
# that LaTeX subset -- NOT a general LaTeX sanitizer. Anything outside
# \frac{}{}, \div, \times, \cdot (e.g. \input, \write18, \catcode) is left
# untouched and will still fail SAFE_EXPRESSION_RE below.
_FRAC_RE = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
_LATEX_OPERATORS = {r"\div": "/", r"\times": "*", r"\cdot": "*"}


def is_safe_math_expression(expr: str) -> bool:
    return bool(SAFE_EXPRESSION_RE.fullmatch(expr))


def delatex(expr: str) -> str:
    """Convert the vetted LaTeX fraction/operator subset to plain
    arithmetic. Used to normalize expr strings before sympify or before
    the safety check that gates LaTeX compilation."""
    prev = None
    while prev != expr:
        prev = expr
        expr = _FRAC_RE.sub(r"((\1)/(\2))", expr)
    for latex_op, plain_op in _LATEX_OPERATORS.items():
        expr = expr.replace(latex_op, plain_op)
    return expr


def is_safe_math_expression_or_latex(expr: str) -> bool:
    """Like is_safe_math_expression, but first strips the vetted LaTeX
    subset above. The original (un-stripped) string is still what gets
    handed to MathTex -- this only validates it's safe to do so."""
    return is_safe_math_expression(delatex(expr))
