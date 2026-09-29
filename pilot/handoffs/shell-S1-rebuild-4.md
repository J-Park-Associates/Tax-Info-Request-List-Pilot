# Shell S1 rebuild 4 (after review 4)

Branch `claude/sharp-goldberg-jmfynk`. Tests only; no code changed.

## Finding

**F1. A moved file's `handle` and `year` on `firm` were not pinned by any
test** (`tracker/api.py:5263-5264`). The only test reading them had a parked
file and no moved one, so setting a moved file's `handle` to `""` and `year`
to `None` passed all 14 firm tests.

## Fixed how

In `test_firm_lists_every_file_it_counts_and_buckets_a_return_with_only_a_file`
(`tests/test_api.py`) every file (the parked `setup.exe` and the moved
`w2.pdf`) now asserts `year == 2025` and a `handle` equal to the handle the
same name has in that return's `state` (`index` for `setup.exe`, `moved` for
`w2.pdf`), and that the handle is not empty.

Mutation-checked on a scratch copy of `tracker/api.py`: the moved row's
`handle` set to `""` and `year` to `None` now fails this test. Restored; the
real `tracker/api.py` is unchanged.
