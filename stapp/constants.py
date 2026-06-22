"""UI copy mirrored from ui/lib/constants.ts."""

SUPPORTED_SCHEMES = (
    "HDFC Mid Cap Fund Direct Growth",
    "HDFC Large Cap Fund Direct Growth",
    "HDFC Small Cap Fund Direct Growth",
    "HDFC Gold ETF Fund of Fund Direct Plan Growth",
    "HDFC Defence Fund Direct Growth",
)

EXAMPLE_QUESTIONS = (
    "What is the expense ratio of HDFC Defence Fund Direct Growth?",
    "What is the exit load on HDFC Mid Cap Fund Direct Growth?",
    "Who manages HDFC Large Cap Fund Direct Growth?",
)

WELCOME_MESSAGE = (
    "Ask factual questions about 5 HDFC mutual fund schemes. "
    "I provide source-backed answers only — no investment advice."
)

# Topics the assistant can answer for each scheme, with a sample question.
ASK_TOPICS = (
    ("Expense ratio", "What is the expense ratio of HDFC Defence Fund Direct Growth?"),
    ("Exit load", "What is the exit load on HDFC Mid Cap Fund Direct Growth?"),
    ("Minimum investment / SIP", "What is the minimum SIP for HDFC Small Cap Fund Direct Growth?"),
    ("Fund manager", "Who manages HDFC Large Cap Fund Direct Growth?"),
    ("Benchmark", "What is the benchmark of HDFC Mid Cap Fund Direct Growth?"),
    ("Tax implications", "What are the tax implications of HDFC Defence Fund Direct Growth?"),
    ("Investment objective", "What is the investment objective of HDFC Small Cap Fund Direct Growth?"),
    ("Overview (NAV, AUM, risk, category)", "What is the risk level of HDFC Defence Fund Direct Growth?"),
    ("Fund house details", "Which AMC manages HDFC Gold ETF Fund of Fund Direct Plan Growth?"),
)

# Question types the assistant will refuse (advisory / comparison / predictions).
CANNOT_ASK = (
    "Should I invest in this fund? (advice)",
    "Which fund is better — Mid Cap or Small Cap? (comparison)",
    "What returns will I get in 5 years? (predictions)",
)

DISCLAIMER = "Facts-only. No investment advice."

FOOTER_NOTE = (
    "Responses are generated automatically based on factual scheme documents."
)
