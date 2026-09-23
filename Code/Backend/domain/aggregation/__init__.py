"""Pure aggregation functions: tagged calls in, figures out.

No I/O, no clock, no randomness, no database and no model. Every function
here takes `CallContext` values and reference facts and returns `Figure`
values, which is what makes the whole layer unit-testable against fixtures
derived from the Call Tag Schema rather than against a pipeline run.
"""
