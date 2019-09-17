[![Build Status](https://travis-ci.com/maarten-dp/fast-alchemy.svg?branch=master)](https://travis-ci.com/maarten-dp/fast-alchemy)
[![Codecov](https://codecov.io/gh/maarten-dp/fast-alchemy/branch/master/graph/badge.svg)](https://codecov.io/gh/maarten-dp/fast-alchemy)
[![PyPI version](https://badge.fury.io/py/fast-alchemy.svg)](https://pypi.org/project/fast-alchemy/)

## Purpose

Fast-alchemy is an easy to use prototyping/testing tool that is able to create SQLAlchemy models and instances on the fly based on a yaml input file. It's able to safely load and unload models at run-time allowing a versatile and flexible workflow.

Use cases include, but are not limited to:
 - Prototyping an application where the ORM model is subject to change
 - Building a number of different model-based testcases without having to clutter your test files with SQLA models you will only use once

 The general philosophy is that the tool should be simple to use for simple to build use-cases, while still allowing the possibility for complex scenarios. This is why the code is built in a way that is non-invasive to already existing code.

## QuickStart

Yaml `ant_colonies.yaml`

```yaml
AntColony:
  ref: name
  definition:
    name: String
    latin_name: String
    queen_size: Float
    worker_size: Float
    color: String
  instances:
    - name: Argentine Ant
      latin_name: Linepithema humile
      queen_size: 1.6
      worker_size: 1.6
      color: brown
    - name: Black House Ant
      latin_name: Ochetellus
      queen_size: 2.5
      worker_size: 2.5
      color: black
```

Python code

```python
import pytest
import sqlalchemy as sa


@pytest.fixture
def fa()
    engine = sa.create_engine('sqlite:///:memory:')
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.bind = engine
    Session = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = sa.orm.scoped_session(Session)

    fa = FastAlchemy(Base, session)
    fa.load('ant_colonies.yaml')
    return fa


def test_it_can_test_my_test(fa):
    ants = fa.session.query(fa.AntColony).all()
    assert len(ants) == 2
```

## What sets this library apart

Populating a database using yaml and SQLA is not an oddity, but so far fast-alchemy seems to be one of the few libraries that is able to provide database population on top of model creation during run-time.


## Defining a model
Before we can start populating our database, we need a database structure. So let's start with defining a model to set us on our way.

Note that the models are being interpreted as we go, this means that every reference you make to other instances or classes must already have been defined on lines prior to the referencing line. An exception to this is back-refs, as they are a chicken and egg conundrum.

```yaml
Formicarium:
  ref: name
  definition:
    name: String
    width: Integer
    collection: relationship|AntCollection
    colonies: Backref|AntColony
```

Seems pretty straightforward, but let's go over it line by line anyway.

### Defining a model name
```yaml
Formicarium:
```
All root keys will be seen as models, in this case we indicate that we want an SQLA model named `Formicarium`.

In the interest of simplicity, all fast-alchemy SQLA models will be given an `id` column as primary key.

### Defining a way to reference instances in the yaml file
```yaml
  ref: name
```
At some point, it would be nice if we could make relations between our models. Since we are unable to control or query IDs inside this yaml definition, it was opted to allow to flag a column as a way to reference individual instances, in case we want to link two instances through a relation.

Here, we're choosing the `name` column as our reference value.


### Defining a column and column type
```yaml
  definition:
    name: String
```
The `definition` keyword indicates the block where we want to define our actual models. The rules here are pretty simple: you define the name you want to give a column, and give it a type. The types are the generic types of SQLAlchemy (https://docs.sqlalchemy.org/en/13/core/type_basics.html) and should be written as the class they are defined. In this case, we're defining a column named `name` and giving it the `String` type

### Defining a relation
```yaml
    collection: relationship|AntCollection
```
Well, we made it this far. let's step it up a notch and define ourselves a relationship. Using the same terminology as SQLAlchemy, we're able to define a relationship by using the keyword... well... `relationship`. We indicate the model, we want a relationship with, by referencing a model that was previously defined in the yaml. Under the hood, we'll create a Many To One relationship with `AntCollection`, using its `id` as a foreign key.

```yaml
    colonies: Backref|AntColony
```
We're also able to indicate that we're interested in creating back-ref for relations that will be defined further in the yaml definition. As previously mentioned, this is the only case where you're able to reference a model that has not yet been defined, if we regard fast-alchemy as interpretative based.


## Defining instances
Cool, cool, great. Now that we know how to create models and we can start spawning some instances.

Because the main goal of this library is to go fast, both model definition and instance creation are able to be done in the same file, but if you're a neat freak, you can define each in a separate file and run them individually. You'll find how to do this later in the readme.

```yaml
AntCollection:
  ref: name
  definition:
    name: String
    location: String
    formicaria: Backref|Formicarium
  instances:
    - name: Antics
      location: My bedroom

Formicarium:
  ref: name
  definition:
    name: String
    width: Integer
    collection: relationship|AntCollection
    colonies: Backref|AntColony
  instances:
    - name: PAnts
      collection: Antics
      width: 3

AntColony:
  ref: name
  definition:
    name: String
    latin_name: String
    queen_size: Float
    worker_size: Float
    color: String
    formicarium: relationship|Formicarium
  instances:
    - name: Argentine Ant
      latin_name: Linepithema humile
      queen_size: 1.6
      worker_size: 1.6
      color: brown
      formicarium: PAnts
    - name: Black House Ant
      latin_name: Ochetellus
      queen_size: 2.5
      worker_size: 2.5
      color: black
      formicarium: PAnts
```

As you can see, pretty straightforward. The `instances` key holds a list of key/value pairs where you populate each column you defined in your model. You can populate a relation column by using the reference column you defined for the related model. In the example above, all models are using the `name` column as their reference column.

Keep in mind that, here as well, the file is read and evaluated with an interpretive mindset. This means that if you reference instances, they will need to have been defined earlier in the file.

### Composite key referencing

If none of your columns are supposed to be unique, you can compose a unique reference by comma separating the columns you wish to use as the reference key.

```yaml
  ref: name,width
```

On the instance creation side, you can then reference your relation as followed:

```yaml
Formicarium:
  ref: name,width
  definition:
    name: String
    width: Integer
  instances:
    - name: PedAntic
      width: 10
    - name: PedAntic
      widt: 15

AntColony:
  ref: name
  definition:
    name: String
    formicarium: relationship|Formicarium
  instances:
    - name: Argentine Ant
      formicarium: PedAntic,10
```

## Interacting with loaded models in your code

While fast-alchemy is loading the models, the model classes are added to the fast-alchemy instance that is creating them. After the load is finished, you can access the model classes as an attribute of the fast-alchemy instance

```python
engine = sa.create_engine('sqlite:///:memory:')
Base = sa.ext.declarative.declarative_base()
Base.metadata.bind = engine
Session = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = sa.orm.scoped_session(Session)

fa = FastAlchemy(Base, session)
fa.load('simple_case.yaml')
session.query(fa.AntColony).all()
```

## Polymorphism

### Yaml definition

As sub-classing is such a natural part of OO programming, it would be a huge hole in the library if it didn't support polymorphism. Defining a polymorphic model is just as easy as sub-classing. You start out by defining your parent model and indicating the polymorphic discriminator. Afterwards you're able to indicate your that child model inherits from the parent by appending the parent model to the model name definition. The polymorphic identities are automatically generated based in the model names

```yaml
Formicarium:
  definition:
    name: String
    formicarium_type: String
    polymorphic:
      "on": formicarium_type

SandwichFormicarium|Formicarium:
  ref: name
  definition:
    height: Integer
```

## Loading and unloading models

Part of being a useful testing tool is the capability of being versatile in the many testcases your wondrous brain can think of. That's why fast-alchemy comes with a built in ability to load models, and then unloads them after your test has, obviously, passed. This allows you to load different models and instances for every test.

I can see I've already convinced you, so let's get on with the show

### Manually cleaning up

```python
import pytest


@pytest.fixture
def fa()
    engine = sa.create_engine('sqlite:///:memory:')
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.bind = engine
    Session = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = sa.orm.scoped_session(Session)

    return FastAlchemy(Base, session)


def simple_case(fa):
    fa.load('simple_case.yaml')
    run_my_test(fa)
    fa.drop_models()


def complex_case(fa):
    fa.load('complex_case.yaml')
    run_my_test(fa)
    fa.drop_models()
```

### Using fast-alchemy's context manager

```python
def simple_case(fa):
    with fa:
        fa.load('simple_case.yaml')
        run_my_test(fa)


def complex_case(fa):
    with fa:
        fa.load('complex_case.yaml')
        run_my_test(fa)
```

### Combining different files

```python
def simple_case(fa):
    fa.load('case_main_part.yaml')
    with fa:
        fa.load('case_secondary_part.yaml')
        run_my_test(fa)
    # case_secondary_part will have unloaded after the context ends
    # retaining the models of case_main_part
```

### Dropping specific models

```python
def simple_case(fa):
    fa.load('simple_case.yaml')
    fa.drop_models(models=['Model1', 'Model2'])
    run_my_test(fa)
```

### Loading models and instances separately

```python
def simple_case(fa):
    fa.load_models('models.yaml')
    fa.load_instances('instances.yaml')
    run_my_test(fa)
```

### Loading instances of predefined models

Fast-alchemy is able to scan for already defined models linked to a certain declared base and use them to populate your database

```python
def simple_case(fa):
    class AntCollection(Base):
        __tablename__ = 'antcollection'
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String())
        location = sa.Column(sa.String())

    fa.load_instances('ant_collections.yaml')
    run_my_test(fa)
```

### Combining complex cases with the simplicity of fast-alchemy

```python
def simple_complex_case(fa):
    class ComplexModel(Base):
        __tablename__ = 'complexmodel'
        id = sa.Column(sa.Integer, primary_key=True)
        # TODO: Add some complexity

    fa.load('simple_case.yaml')
    run_my_test(fa)
```

## Prototyping helpers

At some point, when fiddling and playing to the point you're content, your prototype will start to look good, and you'd like to transition into a more robust implementation. Part of making code more robust is, well... having actual models. But it's such a pain to translate your yaml file into actual SQLA models. That's why fast-alchemy is able to export your yaml models to a completely importable python file, containing all your state-of-the-art models.

```python
from fast_alchemy.export import FastAlchemyExporter

fa = FastAlchemyExporter()
with open('models.py', 'w') as fh:
    fa.export_to_python('instances.yaml', fh)
```

resulting in the following exported file

```python
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

engine = sa.create_engine('sqlite:///:memory:')
Base = declarative_base()
Base.metadata.bind = engine
Session = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = sa.orm.scoped_session(Session)


class AntCollection(Base):
    __tablename__ = 'antcollection'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String())
    location = sa.Column(sa.String())


class Formicarium(Base):
    __tablename__ = 'formicarium'

    __mapper_args__ = {
        'polymorphic_on': 'formicarium_type',
        'polymorphic_identity': 'formicarium'
    }

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String())
    formicarium_type = sa.Column(sa.String())
    width = sa.Column(sa.Integer())
    collection = sa.orm.relationship(AntCollection, backref='formicaria')
    collection_id = sa.Column(sa.Integer, sa.ForeignKey('antcollection.id'))


class SandwichFormicarium(Formicarium):
    __tablename__ = 'sandwichformicarium'

    __mapper_args__ = {
        'polymorphic_identity': 'sandwichformicarium'
    }

    id = sa.Column(sa.Integer, sa.ForeignKey('formicarium.id'), primary_key=True)
    height = sa.Column(sa.Integer())


class FreeStandingFormicarium(Formicarium):
    __tablename__ = 'freestandingformicarium'

    __mapper_args__ = {
        'polymorphic_identity': 'freestandingformicarium'
    }

    id = sa.Column(sa.Integer, sa.ForeignKey('formicarium.id'), primary_key=True)
    depth = sa.Column(sa.Integer())
    anti_escape_barrier = sa.Column(sa.String())


class AntColony(Base):
    __tablename__ = 'antcolony'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String())
    latin_name = sa.Column(sa.String())
    queen_size = sa.Column(sa.Float())
    worker_size = sa.Column(sa.Float())
    color = sa.Column(sa.String())
    formicarium = sa.orm.relationship(Formicarium, backref='colonies')
    formicarium_id = sa.Column(sa.Integer, sa.ForeignKey('formicarium.id'))


Base.metadata.create_all()
```

## Flask-SQLAlchemy integration

Fear not, you're still able to use fast-alchemy if you're developing a flask application. The library behaves exactly the same but instead of importing `FastAlchemy` you can import `FlaskFastAlchemy` to load your models.

```python
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
db = SQLAlchemy(app)

fa = FlaskFastAlchemy(db)
fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
```

## Conclusion

I spent more time writing this readme than I did writing the code.

Worth? maybe... probably... we'll see.
