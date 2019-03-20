import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa

from fast_alchemy import FastAlchemy, FlaskFastAlchemy

ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT_DIR, 'data')


def test_it_can_load_instances():
    engine = sa.create_engine('sqlite:///:memory:', convert_unicode=True)
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.bind = engine
    Session = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = sa.orm.scoped_session(Session)

    fa = FastAlchemy(Base, session)
    with fa:
        fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
    fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
    assert len(session.query(fa.AntCollection).all()) == 3
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
    assert len(fa.AntCollection.query.all()) == 3
    assert len(fa.SandwichFormicarium.query.all()) == 3
    assert len(fa.FreeStandingFormicarium.query.all()) == 2
    assert len(fa.AntColony.query.all()) == 6
