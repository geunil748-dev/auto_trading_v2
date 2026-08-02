# Leakage-safe calibration datasets

`READY_SCORE_POSITIVE_CLOSE_CALIBRATION_DATASET/v1` is an immutable input snapshot for future P4B.2B
calibration. It is not a model or probability artifact. Every dataset contains exactly one horizon
from 1 through 5 and a timezone-aware UTC `dataset_as_of`.

Eligible items are P4A `SCORED_READY` rows with READY source quality and non-null relative score,
rank, and FeatureSnapshot. DEGRADED outcomes may be labeled independently but do not enter this v1
dataset. For each scoring item, selection first applies these Point-in-Time gates:

- outcome `latest_input_available_at <= dataset_as_of`;
- outcome `recorded_at <= dataset_as_of`;
- scoring-run `generated_at <= dataset_as_of`;
- scoring-item `recorded_at <= dataset_as_of`.

The remaining outcome revisions sort by latest input descending, recorded time descending, and
outcome key descending; only the first revision is selected. Items then sort by source session,
scoring run ID, rank, MIC, symbol, and outcome ID. Ordinals start at one. Summary counts preserve
`PROSPECTIVE` and `RETROSPECTIVE_REPLAY` separately and permit a valid `EMPTY` dataset.

Exact dataset retry performs no source query, label creation, dataset calculation, ID generation,
insert, or commit. Labels are independent immutable aggregates; the dataset header and items are one
transaction. P4B.2B may later fit horizon-specific walk-forward sigmoid calibrators from these
snapshots. P4C remains responsible for Recommendations.
