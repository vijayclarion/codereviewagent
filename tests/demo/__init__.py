"""The self-contained half of the demonstration (feature 003, clarification Q2).

Not a test module - `pytest.ini` collects `test_*.py` only, so nothing here runs
unless `tests/integration/test_us3_demo.py` calls it or an operator does:

    python -m tests.demo.run

What it proves, with no server, no credential and no provider:

  * both document formats are read, and every document found is accounted for
  * a rule carrying its own identifier is cited verbatim; one carrying none is
    cited by a derived identifier
  * every acceptance criterion receives a verdict
  * a citation matching no applied rule is reported, not posted
  * every reduction in coverage states itself
  * the same inputs produce the same findings, run after run

What it cannot prove, and does not claim to: that a real provider finds these
faults. The provider is scripted here. Judgement is what the LIVE half of the
demonstration is for, and `demo.md` labels every result with the run it came from.
"""
