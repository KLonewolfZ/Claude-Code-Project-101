"""quantlab - a leakage-resistant ML quantitative trading research system.

The design is driven by the failure modes catalogued in ``docs/ROADMAP_ANALYSIS.md``:

* targets are always **returns**, never price levels (finding 2);
* cross-validation purges and embargoes around each test fold (finding 1);
* a signal formed on the close of bar ``t`` is filled at the open of ``t+1``
  (finding 8);
* strategy quality is judged on economic metrics, deflated for the number of
  trials run (findings 3 and 4).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
