# NanoVox Insights

A call-intelligence application for a general agency in US employee-benefits
insurance: it reads raw call transcripts, extracts a fixed set of facts from
each call with an LLM, joins every call to the employer, broker and member it
belongs to, and renders business insights across seven screens. Three source
documents govern the build, and they outrank each other on different
questions, not on all of them: the v9 workbook wins on definitions — the data
model, the Call Tag Schema, metric formulas, denominators, windows, minimum n,
triggers; Ranjit's Account Signals prototype wins on presentation — layout,
visuals, interaction; `Insights-Worth-Building.docx` wins on scope — which
insights, why, and the principles behind them. Setup instructions, the import
commands, and the architecture will follow as the codebase is built.
