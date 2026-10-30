CREATE TABLE transcripts (
 id TEXT PRIMARY KEY, recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
 parent_id TEXT, producer_job_id TEXT UNIQUE, created_at TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE speaker_names (
 recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
 speaker_id TEXT NOT NULL, display_name TEXT NOT NULL, PRIMARY KEY(recording_id,speaker_id)
);
CREATE TABLE analyses (
 id TEXT PRIMARY KEY, recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
 transcript_id TEXT NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
 producer_job_id TEXT UNIQUE, created_at TEXT NOT NULL, payload TEXT NOT NULL
);
