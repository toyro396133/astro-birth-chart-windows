# People-first workspace — implementation 1

Date: 2026-11-09

## Scope

This change makes the people list the application's first screen. Each person is a stable record, and saved natal charts are nested under that person. It does not change astronomical calculations, interpretation engines, N3, updater behavior, release metadata, or installer workflows.

## Local data layout

The application stores people data under the current user's local application-data directory:

- Windows: `%LOCALAPPDATA%\AstroBirthChart\people\people.json`
- Other platforms: `$XDG_DATA_HOME/AstroBirthChart/people`, or `~/.local/share/AstroBirthChart/people`

The index is versioned (`astro-birth-chart-people`, schema 1) and contains only person/map metadata:
- stable UUID-derived 32-character hexadecimal IDs;
- person name, optional notes and timestamps;
- map ID, display name, primary-map flag, date/place/time summary and timestamps.

The existing validated chart record remains the source of chart inputs. Each map payload is saved as an existing schema-1 `.astrochart.json` record at:

`maps/<person-id>/<map-id>.astrochart.json`

The existing `chart_storage` validation and atomic file writer are reused. The index is also written atomically. Map paths are derived from validated generated IDs; paths from the index are never trusted. The index does not duplicate chart results or interpretation output.

## Behavior

- The people page is the initial application view.
- Users can create and edit people, search the list, select a person, and view that person's saved maps.
- A person can have multiple maps. The first saved map becomes primary; the user can explicitly choose another primary map.
- Names are not unique. Identical names remain separate people because links use stable IDs.
- Starting a new chart from the people page binds it to the selected person.
- Saving a chart requires a valid selected person. A chart opened from a legacy standalone file is deliberately left unassigned; the save flow asks the user to select an existing person or create one first.
- Legacy standalone `.astrochart.json` files remain readable and are not silently moved, deleted, or migrated. Saving an opened legacy chart creates a person-owned copy; the original file remains untouched.
- No person or map deletion is introduced in this phase, avoiding accidental data loss.

## Compatibility and boundaries

- The existing chart record schema is unchanged.
- Existing map calculation, uncertainty handling, PDF/PNG/text/JSON exports, updater, and Windows packaging remain separate.
- The feature is local-only: no network calls, cloud account, telemetry, or remote storage.
- Duplicate-name warnings are implemented in the section above, and immutable map version history is implemented in the section below. Multi-map comparison, bulk import, and backup/restore remain later roadmap items.

## Tests added or updated

- Empty people store and first-screen empty state.
- Person creation/editing and stable IDs.
- Duplicate names remain distinct.
- Multiple maps under one person and exactly one primary map.
- Map update preserves the stable map ID.
- Save is rejected/cancelled until a person is selected.
- Existing standalone chart files still open without implicit assignment.
- Opening a person-owned map restores the person/map relationship.
- Windows GUI smoke now captures the people-first home screen before entering the chart editor.

Windows CI is the authoritative execution environment for the full suite and frozen GUI/build checks. Results must be reported against the final PR HEAD; tests not yet executed must remain NOT_RUN.

## Storage integrity and recovery

All PeopleStore reads and mutations are serialized with a per-store process lock (Windows byte-range lock or POSIX flock), plus a thread lock. A map save/update writes a durable transaction journal containing the old index/payload and intended new index/payload before replacing either live file. The payload is flushed first, then the index; recovery either completes an already-committed index transaction or restores the previous payload when the index commit did not occur. A leftover journal is reconciled before the next read or mutation. Temporary files from interrupted atomic writes are cleaned during recovery.

The store rejects symbolic links and Windows reparse points/junctions at the store root, index, maps directory, person directory and map payload, and verifies canonical containment beneath the configured store root. If people.json is missing while map payloads still exist, the application enters an explicit recovery-required state; it does not show an empty store or rewrite/delete the original map files.

## Similar-name warnings — implementation 2

The person create/edit dialog checks the typed name against the current local people index and shows an inline Hebrew warning. The warning is informational only: the Save button remains enabled, identical names remain separate records with their original stable IDs, and no person is merged or reassigned. Editing excludes the current person's ID from the comparison while still warning about another person with the same or a similar name.

Matching is intentionally conservative and local-only (Python standard library; no new dependency or data-schema change):

- Normalize with Unicode NFKC and `casefold()`, collapse repeated whitespace, treat common dash/maqaf punctuation as spaces, remove common apostrophe/geresh/gershayim/quotation marks, and treat other punctuation as separators.
- A normalized exact match is reported even for short names.
- Approximate matching uses `difflib.SequenceMatcher` with `autojunk=False`, threshold **0.86**, and a minimum normalized length of **6 characters on both names**. Short names therefore do not produce fuzzy warnings.
- The warning lists up to four matching people with their names and short ID hints; it always explains that another person can still be saved.

No automatic merge, deduplication, ID mutation, map reassignment, or storage schema change is performed.


## Map version history — implementation 3

The identity hierarchy is **Person ID → Map ID → immutable Map Versions**. Person and Map IDs remain stable. Updating or restoring a map never creates a new logical map, changes its person relationship, or changes its primary-map flag.

### Storage layout and compatibility

- The existing schema-1 `.astrochart.json` file remains the current payload at `maps/<person-id>/<map-id>.astrochart.json`.
- Immutable snapshots are stored at `maps/<person-id>/<map-id>.versions/<version-id>.astrochart.json`.
- A per-map manifest at `maps/<person-id>/<map-id>.versions.json` records ordered version IDs/numbers, UTC creation timestamps, the current version ID, and an optional `restored_from` link.
- The people index remains schema 1 and the chart record remains schema 1. No existing JSON chart file is rewritten as part of migration.
- A legacy map without a manifest is treated as version 1 on first history access or first update. The current payload is copied into the first immutable snapshot; the original current file and person/map metadata remain in place. The migration uses the same durable transaction journal. If a version directory already contains snapshots but its manifest is missing, the store fails closed and requires recovery rather than guessing.

### Transaction and recovery

A version-changing operation uses a schema-2 journal while retaining schema-1 journal recovery for transactions written by earlier application builds. The commit order is: durable journal → durable immutable snapshot → durable current payload → durable version manifest → durable people index (commit point) → journal removal. Windows replacements retain the approved `MoveFileExW(MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)` path; POSIX replacements/unlinks flush the containing directory and propagate errors. Thread/process locking and path/reparse-point validation cover the complete operation. Recovery rolls back to the old current payload/manifest when the index commit did not occur, or completes the new snapshot/payload/manifest when it did. Older snapshots are never overwritten or removed.

### Version and restore policy

- The first saved map creates version 1.
- A changed validated chart record creates the next monotonically numbered version with a new UUID-derived version ID and UTC timestamp.
- A save whose validated record is exactly equal to the current record creates no extra version. A map display-name-only edit updates metadata without creating a chart-content version.
- Restoring a non-current version appends a new version containing the selected snapshot and records `restored_from`; it never moves the current pointer backward or deletes/rewrites prior snapshots. Restoring the already-current version is a no-op.
- Version history is read-only. There is no delete-history action. The Hebrew RTL history dialog labels each version and date, marks the current version, allows opening a historical snapshot for inspection, and confirms restore. Saving after opening a historical version creates a new current version rather than mutating the opened snapshot.

The per-map version manifest has its own format/schema version (1); the people index and `.astrochart.json` schemas are unchanged.


### Open-chart restore behavior

If the restored map is also the active map in the chart editor, the editor inputs and computed view are recalculated from the newly restored current payload after the storage transaction succeeds. This prevents a hidden stale chart editor from later saving its pre-restore contents over the restored version.


### Recovery bounds and snapshot-directory reconciliation

Recovery applies schema-specific journal limits. Legacy schema-1 journals retain the original `MAX_INDEX_BYTES + 2*262144 + 65536` limit; schema-2 version journals use the same `MAX_INDEX_BYTES + 2*262144 + 2*1024*1024` limit in both the writer and recovery reader. A journal beyond its schema's limit, malformed journal, or unsupported schema fails closed and remains available for diagnosis.

When a version manifest exists, the set of regular `*.astrochart.json` snapshots in its version directory must match the manifest exactly. Missing snapshots, unlisted/orphan snapshots, and unexpected files or directories stop history access with a recovery-required error. Original manifest, payload, and snapshot files are preserved; the application does not guess, delete, or overwrite orphan data. Only recognized atomic-write temporary files (`.astrochart-*.tmp`) are excluded, and the normal recovery cleanup removes them.

Restore transactions are fault-injected at snapshot, payload, manifest, and index phases. Recovery is verified with a fresh `PeopleStore`: pre-index failures restore the old state, while a committed index completes the new restore version and its `restored_from` link. Historical preview followed by Save is tested as a new version under the same Person ID and Map ID; existing snapshots remain byte-identical.
