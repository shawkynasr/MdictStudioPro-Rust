# Sorting findings from the first Mac run

The attached report establishes engine default physical ordering for the exact
synthetic fixture. It is not evidence that either legacy profile is implemented
as a selectable writer option.

| Profile | Full default-order match |
|---|---|
| mdict-utils / MDD | yes |
| mdict-utils / MDX | no |
| MdxBuilder / MDD | no |
| MdxBuilder / MDX | no |

## Confirmed legacy backslash behavior

The original comparator builds its character class with:

```python
regex_strip = re.compile('[%s ]+' % string.punctuation)
```

Because the characters are inserted without escaping, a backslash escapes the
following `]` in the class rather than being a literal backslash to remove.
The observed class strips the other ASCII punctuation but leaves backslashes.
For example `\\images\\A.png` retains its backslashes and loses its dot.
Under the C locale it therefore sorts before `a`. A characterization assertion
now records that exact behavior without changing any golden output.

The uploaded Rust report puts the two backslash-bearing keys later, after `i`.
After excluding just these two keys, the mdict-utils/MDX ordering matches the
recorded Python oracle. This isolates the discrepancy for this fixture. The
engine's internal normalization implementation has NOT been inspected here,
so it does not establish a universal cause or complete normalization policy.

The MdxBuilder profile also differs in non-ASCII case folding. The Python
profile folds ASCII A-Z only. Our baseline already shows `Ä`/`ä` behaving
differently from the Unicode-lowercase profile. These differences remain even
when backslash-bearing keys are excluded from the uploaded report.

## Required next implementation work

1. Inspect the exact mdictlib 0.2.8 writer and lookup normalization source.
2. Determine its extension points for sorting, header flags and block summaries.
3. Specify intentional legacy compatibility versus corrections (including the
   backslash regex quirk and locale dependence).
4. Implement profiles through a supported API or a minimal auditable engine patch.
   Pre-sorting input is insufficient if the writer sorts again.
5. Test physical order, duplicate tie handling, summary boundaries, and exact /
   normalized lookup. Check independent reader applications.

A physical ordering difference alone does not prove a reader failure. Do not
change lookup normalization or preserve a legacy defect without measuring its
effect on generated dictionary search.
