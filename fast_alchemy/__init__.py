import os
from collections import defaultdict, namedtuple
import copy

from sqlalchemy.inspection import inspect as sqla_inspect

from .helpers import ordered_load, scan_current_models

ClassInfo = namedtuple('ClassInfo', 'class_name,inherits_class,inherits_name')
FieldInfo = namedtuple('FieldInfo', 'field_name,field_definition,field_args')
NO_COLUMN_FOR = ['relationship']


class FieldBuilder:
    def __init__(self, db):
        self.db = db

    def build_field(self, field_info, class_name, backrefs):
        fields = {}
        kwargs = {}

        if field_info.field_definition == 'relationship':
            fk_name, fk = self._build_relation(field_info)
            fields[fk_name] = fk
            kwargs['backref'] = backrefs[class_name][field_info.field_args[0]]

        field_type = getattr(self.db, field_info.field_definition)
        field = field_type(*field_info.field_args, **kwargs)
        if field_info.field_definition not in NO_COLUMN_FOR:
            field = self.db.Column(field_info.field_name, field)
        fields[field_info.field_name] = field
        return fields

    def _build_relation(self, field_info):
        fk_name = '{}_id'.format(field_info.field_name)
        fk_relation = '{}.id'.format(field_info.field_args[0].lower())
        fk = self.db.Column(
            fk_name, self.db.Integer, self.db.ForeignKey(fk_relation))
        return fk_name, fk


class ClassBuilder:
    def __init__(self, db, field_builder=None):
        self.db = db
        self.backrefs = defaultdict(dict)
        if not field_builder:
            field_builder = FieldBuilder(db)
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
                self.backrefs[field_info.field_args[0]][class_name] = field_name
            else:
                yield field_info

    def _prepare_polymorphic(self, field_def):
        mapper_args = {}
        for key, val in field_def.items():
            mapper_args['polymorphic_{}'.format(key)] = val
        return mapper_args

    def _build_pk(self, class_info):
        pk_args = [self.db.Integer]
        if self.db.Model not in class_info.inherits_class:
            inherits_name = class_info.inherits_name
            fk_id = '{}.id'.format(class_info.inherits_name.lower())
            pk_args.append(self.db.ForeignKey(fk_id))
        return self.db.Column(*pk_args, primary_key=True)
        
    def build_class(self, class_info, fields):
        class_name = class_info.class_name
        tablename = class_name.lower()

        class_attributes = {
            '__tablename__': tablename,
            'id': self._build_pk(class_info)
        }
        if 'polymorphic' in fields:
            definition = self._prepare_polymorphic(fields.pop('polymorphic'))
            class_attributes['__mapper_args__'] = definition

        for field_info in self._parse_fields(fields, class_name):
            class_attributes.update(
                self.field_builder(field_info, class_name, self.backrefs))

        Klass = type(class_name, class_info.inherits_class, class_attributes)
        setattr(self.db, class_name, Klass)
        return class_name


class InstanceLoader:
    def __init__(self, db, classes):
        self.db = db
        self.classes = classes

    def _scan_relations(self, klass):
        relations = []
        for rel in sqla_inspect(klass).relationships:
            if rel.direction.name == 'MANYTOONE':
                relations.append(rel.key)
        return relations

    def load_instance(self, class_info, ref_name, instances, instance_refs):
        klass = self.classes[class_info.class_name]
        for definition in instances:
            for relation in self._scan_relations(klass):
                related_instance = instance_refs[definition[relation]]
                definition[relation] = related_instance
            instance = klass(**definition)
            instance_refs[definition[ref_name]] = instance


class FastAlchemy:
    def __init__(self, db, class_builder=None, instance_loader=None):
        self.db = db

    def _parse_class_definition(self, class_definition):
        inherits_class = (self.db.Model,)
        class_name = class_definition
        inherits_name = None
        if '|' in class_definition:
            class_name, inherits_name = class_definition.split('|')
            inherits_class = (getattr(self.db, inherits_name),)
        return ClassInfo(class_name, inherits_class, inherits_name)

    def _load_file(self, file_or_raw):
        raw = file_or_raw
        if isinstance(file_or_raw, str):
            with open(file_or_raw, 'r') as fh:
                raw = ordered_load(fh)
        return raw
        
    def load(self, filepath):
        raw = self._load_file(filepath)
        self.load_models(raw)
        self.load_instances(raw)

    def load_models(self, file_or_raw, class_builder=None):
        if not class_builder:
            class_builder = ClassBuilder(self.db).build_class

        classes = []
        raw_models = self._load_file(file_or_raw)

        for class_definition, fields in raw_models.items():
            class_info = self._parse_class_definition(class_definition)
            class_builder(class_info, fields['definition'])
        self.db.create_all()

    def load_instances(self, file_or_raw, instance_loader=None):
        if not instance_loader:
            classes = scan_current_models(self.db)
            instance_loader = InstanceLoader(self.db, classes).load_instance

        raw_instances = self._load_file(file_or_raw)
        instance_refs = {}
        for class_definition, fields in raw_instances.items():
            if not fields.get('instances'):
                continue
            class_info = self._parse_class_definition(class_definition)
            instance_loader(
                class_info, fields['ref'], fields['instances'], instance_refs)
        self.db.session.add_all(instance_refs.values())
        self.db.session.commit()
