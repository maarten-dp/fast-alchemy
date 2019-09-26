import importlib
import os
import tempfile

import pytest
import sqlalchemy as sa
from fast_alchemy import FastAlchemy, FlaskFastAlchemy
from fast_alchemy.export import FastAlchemyExporter
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT_DIR, 'data')


@pytest.fixture(scope='function')
def temp_file(request):
    _, path = tempfile.mkstemp(suffix='.py')

    def remove_file():
        os.remove(path)

    request.addfinalizer(remove_file)
    return path


def test_it_can_load_instances():
    engine = sa.create_engine('sqlite:///:memory:')
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.bind = engine
    Session = sa.orm.sessionmaker(
        autocommit=False, autoflush=False, bind=engine)
    session = sa.orm.scoped_session(Session)

    fa = FastAlchemy(Base, session)
    with fa:
        fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
    fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
    assert len(session.query(fa.AntCollection).all()) == 4
    assert len(session.query(fa.SandwichFormicarium).all()) == 3
    assert len(session.query(fa.FreeStandingFormicarium).all()) == 2
    assert len(session.query(fa.AntColony).all()) == 6


def test_it_can_load_from_flask_sqlalchemy():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db = SQLAlchemy(app)

    fa = FlaskFastAlchemy(db)
    with fa:
        fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
    fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
    assert len(fa.AntCollection.query.all()) == 4
    assert len(fa.SandwichFormicarium.query.all()) == 3
    assert len(fa.FreeStandingFormicarium.query.all()) == 2
    assert len(fa.AntColony.query.all()) == 6


def test_it_can_export_models_to_python_code(temp_file):
    fa = FastAlchemyExporter()
    with open(os.path.join(DATA_DIR, temp_file), 'w') as fh:
        fa.export_to_python(os.path.join(DATA_DIR, 'instances.yaml'), fh)

    spec = importlib.util.spec_from_file_location('models', temp_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fa = FastAlchemy(module.Base, module.session)
    instances = fa.load_instances(os.path.join(DATA_DIR, 'instances.yaml'))
    session = module.session
    session.add_all(instances.values())
    session.commit()
    assert len(session.query(module.AntCollection).all()) == 4
    assert len(session.query(module.SandwichFormicarium).all()) == 3
    assert len(session.query(module.FreeStandingFormicarium).all()) == 2
    assert len(session.query(module.AntColony).all()) == 6
