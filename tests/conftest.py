import pytest
from meetinglog.config import Settings
from meetinglog.db import Database


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", models_dir=tmp_path / "models", _env_file=None)


@pytest.fixture
def db(settings):
    database = Database(settings.database_path)
    database.migrate()
    return database


@pytest.fixture
def input_service(settings, db):
    from meetinglog.recordings.service import InputService

    return InputService(settings, db)
