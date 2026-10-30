ALTER TABLE recordings ADD COLUMN initial_job_id TEXT;
CREATE INDEX pending_deletions ON recordings(deleted_at) WHERE deleted_at IS NOT NULL;
