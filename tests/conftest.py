import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


@pytest.fixture(scope="session")
def engine():
    test_engine = create_engine(settings.database_url)
    if test_engine.dialect.name != "postgresql":
        test_engine.dispose()
        pytest.skip("PostgreSQL integration tests require DATABASE_URL")

    yield test_engine

    test_engine.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
