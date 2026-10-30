CREATE INDEX analyses_history ON analyses(recording_id,created_at);
CREATE INDEX transcripts_history ON transcripts(recording_id,created_at);
