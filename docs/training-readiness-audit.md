# Training Readiness Audit

`TrainingReadinessAuditService` audits exactly one persisted P4B.2A
`ProbabilityCalibrationDataset` for each `RunTrainingReadinessAuditCommand`. The required input is
an explicit `probability_calibration_dataset_id`; wall-clock “latest dataset” discovery is not
supported. The batch command accepts multiple unique explicit IDs and groups deterministic results
by horizon.

The service uses the existing `ProbabilityCalibrationDatasetRepository`. One added read method
selects canonical scoring, P3 pipeline, FeatureSnapshot, outcome, and label lineage. SQLAlchemy and
DotNet reuse the same SQLAlchemy Core statement and mapping. The application never calls
`commit()`; normal UoW exit rolls the read transaction back.

## Result boundary

Each result contains:

- exact dataset ID/key/digest/status/as-of, horizon, provider, calendar, and policy versions;
- item, session, symbol/listing, date-span, observation-mode, and class counts;
- null/invalid score, duplicate source, canonical order, and content-digest checks;
- scoring READY/DEGRADED/skipped, snapshot READY/DEGRADED, volume, outcome, label, policy,
  provider, calendar, and exclusion facts;
- provider-specific quality distribution and coverage before/after READY-only filtering;
- legacy calibration readiness separated from MVP trade-model readiness;
- an ordered machine-readable blocker list and explicit not-derivable fields.

FeatureSnapshots support only READY and DEGRADED. A P3 `DATA_INSUFFICIENT` item has no
FeatureSnapshot, so “FeatureSnapshot DATA_INSUFFICIENT count” is
`NOT_DERIVABLE_FROM_CURRENT_SCHEMA`; the provider distribution can still report the canonical P3
pipeline count. The schema also cannot prove that a volume-degraded row would be READY under a
future price-only policy. That field is
`COUNTERFACTUAL_PRICE_ONLY_ELIGIBILITY_NOT_DERIVABLE`.

## Legacy research thresholds

The legacy fit check requires 300 items, 60 source sessions, 60 POSITIVE, and 60 NOT_POSITIVE.
Replay evaluation requires 150 items, 20 sessions, and 30 of each class. Prospective evaluation
requires 100 items, 20 sessions, and 20 of each class. Results are restricted to:

- `LEGACY_CALIBRATION_DATA_READY`
- `LEGACY_CALIBRATION_DATA_INSUFFICIENT`
- `LEGACY_CALIBRATION_CLASS_IMBALANCED`
- `LEGACY_CALIBRATION_PROSPECTIVE_INSUFFICIENT`
- `LEGACY_CALIBRATION_SOURCE_INELIGIBLE`

Even `LEGACY_CALIBRATION_DATA_READY` means only that the legacy positive-forward-close research
question has enough data. It is not evidence for an executable, cost-adjusted trade model.

MVP readiness is always `MVP_TRADE_MODEL_NOT_READY` in this slice. Its blockers include missing
execution-aligned outcome and cost-adjusted label policies, unfrozen costs, next-open/fixed-hold
results, multi-year calendar/backfill, prospective operation, the data-quality decision, baseline
evaluation, and both unresolved data-quality implementation options.

## CLI and reports

With the development DB URL available only through the canonical environment variable:

```powershell
python scripts/run_training_readiness_audit.py `
  --dataset-id <UUID> `
  --dataset-id <UUID> `
  --output-dir <repository-external-directory>
```

The default output directory is under the system temporary directory, outside the repository.
Outputs are UTF-8 without BOM and atomically replaced:

- `training_readiness_audit.json`
- `training_readiness_audit.md`
- `training_readiness_audit.sha256`

Ordering is stable, percentages are Decimal-derived strings, zero denominators are explicit, and
reports contain no DB URL, credential, provider response, or secret. The command performs no
provider/network, scheduler, Telegram, Recommendation, model-fitting, or order operation.
