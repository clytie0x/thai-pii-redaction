# YRSS evaluation v2 evidence

Protocol: [pre-registration](../../../docs/decisions/2026-11-13-yrss-eval-v2.md).
Synthetic data only. Nothing here is a held-out result.

## Dev baseline, before any detector change

`dev-baseline.json` is the harness report for the dev split (100 families,
300 documents, 1,188 entities) on the detector as it stood before this
campaign changed it. The dev split is for finding errors. Its scores must not
be cited as accuracy.

```bash
python -m benchmark.yrss_v2 --split dev \
  --systems aiguard,regex,crf-ner,wangchanberta-ner,presidio,aiguard-no-fp,aiguard-no-tb,aiguard-no-address_merge \
  --json research/yrss2026/v2/dev-baseline.json
```

Presidio and WangchanBERTa need the optional packages at the versions in
`docs/benchmark/per-entity-results.md`. The LLM comparator was not run.

## Error inventory for the full system on dev

Counted from predictions, with no document text or values kept.

- Out-of-scheme predictions, counted as false positives in the unrestricted
  view: DATE 245, ORGANIZATION 60, LOCATION 58, ID_NUMBER 53. These are labels
  the product emits on purpose. They are why unrestricted precision is far
  below the shared-11 precision.
- No negative document is left untouched (0 of 60). Most hits there are the
  same four labels; 18 are THAI_ID on 13-digit numbers that fail the check
  digit.
- Missed entirely: NAME 99 (about 60 are names in Latin script), VEHICLE_PLATE
  14, DATE_OF_BIRTH 12.
- Covered but with another label: DATE_OF_BIRTH as DATE 9, DRIVER_LICENSE as
  ID_NUMBER 6, BANK_ACCOUNT as ID_NUMBER 3, PHONE inside an EMAIL span 3.
- In-scheme false positives: NAME 72, ADDRESS 31, THAI_ID 27.
