# Shared across every module that sends listing description text to an LLM
# (groq_client's summarizer, input_review's supervisor) — one budget, not two
# independently-maintained copies of the same number.
MAX_DESCRIPTION_CHARS = 500
