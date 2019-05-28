from collections import defaultdict

import sqlalchemy as sa
from fast_alchemy import ClassInfo, FastAlchemy, FieldInfo, Options

NO_COLUMN_FOR = ['relationship']
FIELD_LOCATION_STRINGS = {sa: 'sa', sa.orm: 'sa.orm'}

COLUMN_TEMPLATE = """    {} = sa.Column({}{})"""
MAPPER_TEMPLATE = """    __mapper_args__ = {{
        {}
    }}
"""
SESSION_CREATION_TEMPLATE = """import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

engine = sa.create_engine('sqlite:///:memory:')
Base = declarative_base()
Base.metadata.bind = engine
Session = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = sa.orm.scoped_session(Session)"""


class FastAlchemyExporter(FastAlchemy):
    def __init__(self, **kwargs):
        kwargs['field_builder'] = kwargs.pop('field_builder', FieldExporter)
        kwargs['class_builder'] = kwargs.pop('class_builder', ClassExporter)
        self.options = Options(**kwargs)
        self.class_registry = {}
        self.in_context = False

    def export_to_python(self, file_or_raw, fileobj):
        self.load_models(file_or_raw)
        fileobj.write(SESSION_CREATION_TEMPLATE)
        for class_definition in self.class_registry.values():
            fileobj.write('\n\n\n')
            fileobj.write(class_definition)
        fileobj.write('\n\n\nBase.metadata.create_all()\n')

    def create_models(self, *args, **kwargs):
        pass

    def _parse_class_definition(self, class_definition):
        inherits_class = ('Base', )
        class_name = class_definition
        inherits_name = None
        if '|' in class_definition:
            class_name, inherits_name = class_definition.split('|')
            inherits_class = (inherits_name, )
        return ClassInfo(class_name, inherits_class, inherits_name)


class FieldExporter:
    def build_field(self, field_info, class_name, backrefs):
        fields = []
        kwargs = {}

        if field_info.field_definition == 'relationship':
            fields.append(self._build_relation(field_info))
            kwargs['backref'] = "'{}'".format(
                backrefs[class_name][field_info.field_args[0]])

        field_type = None
        for location in FIELD_LOCATION_STRINGS:
            if hasattr(location, field_info.field_definition):
                location_str = FIELD_LOCATION_STRINGS[location]
                field_type = '{}.{}'.format(location_str,
                                            field_info.field_definition)
        if not field_type:
            raise Exception('{} could not be found'.format(field_type))

        field_args = ', '.join(field_info.field_args)
        field_kwargs = ', '.join(
            ['{}={}'.format(k, v) for k, v in kwargs.items()])
        field_params = field_args or field_kwargs
        if field_args and field_kwargs:
            field_params = ', '.join([field_args, field_kwargs])
        field = '{}({})'.format(field_type, field_params)

        if field_info.field_definition not in NO_COLUMN_FOR:
            field = COLUMN_TEMPLATE.format(field_info.field_name, field, '')
        else:
            field = """    {} = {}""".format(field_info.field_name, field)
        fields.append(field)
        return sorted(fields)

    def _build_relation(self, field_info):
        fk_name = '{}_id'.format(field_info.field_name)
        fk_relation = '{}.id'.format(field_info.field_args[0].lower())

        relation_field = COLUMN_TEMPLATE.format(
            fk_name, 'sa.Integer', ", sa.ForeignKey('{}')".format(fk_relation))

        return relation_field


class ClassExporter:
    def __init__(self, db, field_builder):
        self.db = db
        self.backrefs = defaultdict(dict)
        self.field_builder = field_builder.build_field

    def _parse_field(self, field_name, field_definition):
        field_args = []
        if '|' in field_definition:
            field_definition, args = field_definition.split('|')
            field_args = args.split(',')
        return FieldInfo(field_name, field_definition, field_args)

    def _parse_fields(self, fields, class_name):
        for field_name, field_definition in fields.items():
            field_info = self._parse_field(field_name, field_definition)
            if field_info.field_definition == 'Backref':
                self.backrefs[field_info.
                              field_args[0]][class_name] = field_name
            else:
                yield field_info

    def _prepare_polymorphic(self, field_def):
        mapper_args = {}
        for key, val in field_def.items():
            mapper_args['polymorphic_{}'.format(key)] = "'{}'".format(val)
        return mapper_args

    def _build_pk(self, class_info):
        pk_args = []
        if 'Base' not in class_info.inherits_class:
            fk_id = '{}.id'.format(class_info.inherits_name.lower())
            pk_args.append("sa.ForeignKey('{}')".format(fk_id))
        pk_args.append('primary_key=True')
        return COLUMN_TEMPLATE.format('id', 'sa.Integer, ', ', '.join(pk_args))

    def build_class(self, class_info, fields):
        class_name = class_info.class_name
        tablename = class_name.lower()

        attributes = [
            "    __tablename__ = '{}'\n".format(tablename),
        ]
        if class_info.inherits_name or 'polymorphic' in fields:
            polymorphic_def = fields.pop('polymorphic', {})
            polymorphic_def['identity'] = class_info.class_name.lower()
            definition = self._prepare_polymorphic(polymorphic_def)
            kwargs = ',\n        '.join(
                ["'{}': {}".format(k, v) for k, v in definition.items()])
            attributes.append(MAPPER_TEMPLATE.format(kwargs))

        attributes.append(self._build_pk(class_info))

        for field_info in self._parse_fields(fields, class_name):
            attributes.extend(
                self.field_builder(field_info, class_name, self.backrefs))

        class_attributes = '\n'.join(attributes)
        class_def = 'class {}({}):\n{}'.format(
            class_name, class_info.inherits_class[0], class_attributes)
        return class_def
