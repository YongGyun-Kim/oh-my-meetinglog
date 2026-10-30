ALTER TABLE job_events ADD COLUMN source_key TEXT;
CREATE UNIQUE INDEX unique_job_event_source ON job_events(job_id, source_key) WHERE source_key IS NOT NULL;
