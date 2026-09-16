# Form-type checklists (generated)

One CSV per return type, in the manifest's own columns, for reading in Excel.

**Do not edit these files.** They are generated from the catalog in
`tracker/templates.py`, which is the only source of truth for what each form
asks for and how each document is recognised:

```
python -m tracker.templates export    # regenerate after editing the catalog
python -m tracker.templates check     # exit 1 if a CSV has drifted
```

`tests/test_templates.py` runs the same check, so a hand edit here fails the
suite. The desktop app's wizard and `python -m tracker.rollover --form` read
the catalog directly, never these files.
