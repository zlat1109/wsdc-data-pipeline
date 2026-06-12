# Parser CSV output (input for load.py in CI)

Place the five main CSV files here before running the **Full WSDC parse pipeline** workflow:

- `dancers_points_info.csv`
- `dancer_role_info.csv`
- `dancers_results_info.csv`
- `location_info.csv`
- `events_wsdc.csv`

Optional history sources:

- `changed_dancers_points_info.csv` or `changed_dancer_points_info.csv`

This directory is gitignored — commit only when intentionally triggering a CI load,
or upload via a branch for automation testing.
