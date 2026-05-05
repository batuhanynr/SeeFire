# M7 Logging & Output

Current purpose: local persistence for events, helper JSON save/load, and JPEG snapshot storage.

## Implemented Today

- SQLite initialization with WAL mode
- `log_event()`
- `get_events()`
- `save_map()`
- `load_map()`
- `save_snapshot()`

## Notes

- Persistent paths come from `config.py`
- Default storage location is repo-local `runtime_data/` unless `SEEFIRE_DATA_DIR` is set
- `save_map()` / `load_map()` still exist as generic helpers, even though current M5 navigation no longer performs occupancy-grid exploration

Older README text that assumed `/data` and non-WAL SQLite behavior is outdated.
