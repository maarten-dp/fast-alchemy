## Purpose

Fast-alchemy is an easy to use prototyping/testing tool that is able to create SQLAlchemy models and instances on the fly based on a yaml input file. It's able to safely load and unload models at runtime allowing a versatile and flexible workflow.

Use cases include, but are not limited to:
 - Prototyping an application where the ORM model is subject to change
 - Building a number of different model-based testcases without having to clutter your test files with SQLA models
 - 

 The general philosophy is that the tool should be simple to use for simple to build usecases, while still allowing the posibility for complex scenarios. This is why the code is built in a way that is non-invasive to already existing code.

## What sets this library apart

Populating a database using yaml and SQLA is not an odity, but so far fast-alchemy seems to be one of the few libraries that is able to provide database population on top of model creation during runtime.


## Defining a model
Before we can start populating our database, we need a database structure. So let's start with defining a model to set us on our way. 

Note that the models are being interpretted as we go, that means that every reference you make to other instances or classes must already have been define on lines prior to the referencing line. An exception to this is backrefs, as they are a chicken and egg conundrum.

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
All root keys will be seen as models, in this case we indicate that we want an SQLA model named 'AntCollection'. In the intrest of simplicity, all fast-alchemy SQLA models will be given an `id` column as primary key.

### Defining a future way to reference instances in the yaml file
```yaml
  ref: name
```
At some point, it would be nice if we could make relations between our models.  Since we are unable to control or query ids inside this yaml definition, it was opted to allow to flag a column as a way to reference individual instances, in case we want to link two instances through a relation.

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
Well, we made it this far. let's step it up a notch and define ourselves a relationship. Using the same terminology as SQLAlchemy, we're able to define a relationship by using the keyword... well... `relationship`. We indicate the model, we want a relationship with, by referencing a model that was previously defined in the yaml. Behind the hood, we'll create a Many To One relationship with `AntCollection`, using its `ìd` as a foreign key.

```yaml
    colonies: Backref|AntColony
```
We're also able to indicate that we're interested in creating backref for relations that will be defined further in the yaml definition. As previously mentioned, this is the only case where you're able to reference a model that has not yet been defined, if we regard fast-alchemy as an interpretative based parser.

### SQLAlchemy equivalent
If we run the above yaml through fast-alchemy, it would be the equivalent of the following python code, using SQLAlchemy

```python
import sqlalchemy as sa

engine = sa.create_engine('sqlite:///:memory:', convert_unicode=True)
Base = sa.ext.declarative.declarative_base()
Base.metadata.bind = engine
Session = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = sa.orm.scoped_session(Session)

class Formicarium(Base):
    name = sa.Column(sa.String())
    width = sa.Column(sa.Integer())

    collection_id = sa.Column(sa.Integer, sa.ForeignKey('antcollection.id'))
    collection = sa.orm.relationship('AntCollection') # if a backref was defined on Antcollection, it would be added here.

    # colonies will be added as a backref in the AntColony relationship
```

## Defining instances
Cool, cool, great. Now that we know how to create models and we can start spawning some instances.

Because the main goal of this library is to go fast, both model definition and instance creation is able to be done in the same file, but if you're a neat freak, you can define each in a seperate file and run them individually. You'll find how to do this later in the readme.

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

As you can see, pretty straigtforward. The `instances` key holds a list of key/value pairs where you populate each column you defined in your models. You can populate a relation column by using the reference column you defined for the related model. In the example above, all models are using the `name` column as their reference column.

Keep in mind that, here as well, the file is read and evaluated in an interpretive mindset. This means that if you reference instances, they will need to have been defined earlier in the file.

## Polymorphism

### Yaml definition

As subclassing is such a natural part of programming, it would be a huge hole in the library if it didn't support polymorphism. Defining a polymorphic model is just as easy as subclassing. You start of by defining your parent model and indicating the polymorphic descriminator. Afterwards you're able to indicate your child model inherits from the parent by appending the parent model to the model name definition. The polymorphic identities are automatically generated based in the model names

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

### SQLAlchemy equivalent
If we run the above yaml through fast-alchemy, it would be the equivalent of the following python code, using SQLAlchemy

```python
import sqlalchemy as sa

engine = sa.create_engine('sqlite:///:memory:', convert_unicode=True)
Base = sa.ext.declarative.declarative_base()
Base.metadata.bind = engine
Session = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = sa.orm.scoped_session(Session)

class Formicarium(Base):
    name = sa.Column(sa.String())
    formicarium_type = sa.Column(sa.String())

    __mapper_args__ = {
        'polymorphic_on': 'formicarium_type',
        'polymorphic_identity': 'formicarium',
    }

class SandwichFormicarium(Formicarium):
    height = sa.Column(sa.Integer())

    __mapper_args__ = {
        'polymorphic_identity': 'sandwichformicarium',
    }
```
