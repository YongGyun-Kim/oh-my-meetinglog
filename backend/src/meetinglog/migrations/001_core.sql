CREATE TABLE recordings (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT NOT NULL,
 input_state TEXT NOT NULL, duration_ms INTEGER, created_at TEXT NOT NULL,
 generation INTEGER NOT NULL DEFAULT 0, deleted_at TEXT,
 original_path TEXT, normalized_path TEXT, original_mime TEXT, filename TEXT,
 byte_count INTEGER NOT NULL DEFAULT 0, current_transcript_id TEXT, error_code TEXT
);
CREATE TABLE chunks (
 recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
 sequence INTEGER NOT NULL, digest TEXT NOT NULL, byte_count INTEGER NOT NULL,
 PRIMARY KEY(recording_id, sequence)
);
CREATE TABLE jobs (
 id TEXT PRIMARY KEY, recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
 transcript_id TEXT, kind TEXT NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL,
 generation INTEGER NOT NULL, mode TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 heartbeat TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
 speech_artifact TEXT, analysis_artifact TEXT, error_code TEXT, error_message TEXT
);
CREATE UNIQUE INDEX one_active_job ON jobs(recording_id) WHERE state IN ('queued','running','interrupted');
CREATE TABLE job_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, stage TEXT NOT NULL, event TEXT NOT NULL, metadata TEXT NOT NULL
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
