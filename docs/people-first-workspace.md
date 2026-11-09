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
- This phase does not yet add duplicate-name warnings, map version history/diff, multi-map comparison, bulk import, or backup/restore. Those remain later roadmap items.

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

