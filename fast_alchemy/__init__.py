from collections import defaultdict, namedtuple

import sqlalchemy as sa
from sqlalchemy import and_, or_, orm
from sqlalchemy.inspection import inspect as sqla_inspect

from .helpers import load_file, scan_current_models

ClassInfo = namedtuple('ClassInfo', 'class_name,inherits_class,inherits_name')
FieldInfo = namedtuple('FieldInfo', 'field_name,field_definition,field_args')
NO_COLUMN_FOR = ['relationship']
FIELD_LOCATIONS = [sa, orm]
OPTIONS = None


class Options:
    def __init__(self, **kwargs):
        self.instance_loader = kwargs.pop('instance_loader', InstanceLoader)
        self.class_builder = kwargs.pop('class_builder', ClassBuilder)
        self.field_builder = kwargs.pop('field_builder', FieldBuilder)
        self.file_loader = kwargs.pop('file_loader', load_file)
        self.separator = kwargs.pop('separator', ',')


class FieldBuilder:
    def build_field(self, field_info, class_name, backrefs):
        fields = {}
        kwargs = {}

        if field_info.field_definition == 'relationship':
            fk_name, fk = self._build_relation(field_info)
            fields[fk_name] = fk
            kwargs['backref'] = backrefs[class_name][field_info.field_args[0]]

        field_type = None
        for location in FIELD_LOCATIONS:
            if hasattr(location, field_info.field_definition):
                field_type = getattr(location, field_info.field_definition)
        if not field_type:
            raise Exception('{} could not be found'.format(field_type))

        field = field_type(*field_info.field_args, **kwargs)
        if field_info.field_definition not in NO_COLUMN_FOR:
            field = sa.Column(field_info.field_name, field)
        fields[field_info.field_name] = field
        return fields

    def _build_relation(self, field_info):
        fk_name = '{}_id'.format(field_info.field_name)
        fk_relation = '{}.id'.format(field_info.field_args[0].lower())
        fk = sa.Column(fk_name, sa.Integer, sa.ForeignKey(fk_relation))
        return fk_name, fk


def get_ref_from_instance(instance, ref, sep):
    keys = ref.split(sep)
    values = [instance.get(k, 'None') for k in keys]
    return dict(zip(keys, values))


def get_definition_from_physical_ref(instance_ref, ref, sep):
    keys = ref.split(sep)
    values = instance_ref.split(sep)
    return dict(zip(keys, values))


def scan_attributes(klass):
    attributes = []
    for column in sqla_inspect(klass).columns:
        attributes.append(column.key)
    return attributes


def scan_relations(klass):
    relations = []
    for rel in sqla_inspect(klass).relationships:
        if rel.direction.name == 'MANYTOONE':
            relations.append((rel.key, rel.mapper.class_.__name__))
    return relations


def scan_all_relations(klass):
    relations = []
    for rel in sqla_inspect(klass).relationships:
        relations.append((rel.key, rel.mapper.class_.__name__))
    return relations


def instance_to_ref(instances, instance, ref, sep, base_model):
    physical_ref = []
    keys = ref.split(sep)
    for key in keys:
        attr = getattr(instance, key)
        if isinstance(attr, base_model):
            klass_name = attr.__class__.__name__
            ref = instances[klass_name]['ref']
            attr = instance_to_ref(instances, attr, ref, sep, base_model)
        physical_ref.append(str(attr))
    return sep.join(physical_ref)


class ClassBuilder:
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
            mapper_args['polymorphic_{}'.format(key)] = val
        return mapper_args

    def _build_pk(self, class_info):
        pk_args = [sa.Integer]
        if self.db.Model not in class_info.inherits_class:
            fk_id = '{}.id'.format(class_info.inherits_name.lower())
            pk_args.append(sa.ForeignKey(fk_id))
        return sa.Column(*pk_args, primary_key=True)

    def build_class(self, class_info, fields):
        class_name = class_info.class_name
        tablename = class_name.lower()

        class_attributes = {
            '__tablename__': tablename,
            'id': self._build_pk(class_info)
        }
        if class_info.inherits_name or 'polymorphic' in fields:
            polymorphic_def = fields.pop('polymorphic', {})
            polymorphic_def['identity'] = class_info.class_name.lower()
            definition = self._prepare_polymorphic(polymorphic_def)
            class_attributes['__mapper_args__'] = definition

        for field_info in self._parse_fields(fields, class_name):
            class_attributes.update(
                self.field_builder(field_info, class_name, self.backrefs))

        Klass = type(class_name, class_info.inherits_class, class_attributes)
        setattr(self.db, class_name, Klass)
        return Klass


class InstanceLoader:
    def __init__(self, db, classes, ref_mapping, separator, auto_load=False):
        self.db = db
        self.classes = classes
        self.auto_load = auto_load
        self.ref_mapping = ref_mapping
        self.sep = separator

    def load_instance(self, class_info, ref_name, instances, instance_refs):
        klass_name = class_info.class_name
        klass = self.classes[klass_name]
        # create the instances so that they are available in the ref
        for definition in instances:
            ref = self.build_ref(klass_name, definition, ref_name)
            if ref in instance_refs:
                continue
            instance = self.build_instance(klass, definition, instance_refs,
                                           ref_name)
            instance_refs[ref] = instance

    def link_relations(self, class_info, ref_name, instances, instance_refs):
        klass_name = class_info.class_name
        klass = self.classes[klass_name]
        for definition in instances:
            ref = self.build_ref(klass_name, definition, ref_name)
            instance = instance_refs[ref]
            for relation, rel_klass_name in scan_relations(klass):
                if relation in definition:
                    self.build_relation(instance, rel_klass_name, definition,
                                        instance_refs, relation)

    def get_relation_candidates(self, parent_class):
        candidates = [parent_class]
        for subclass in self.classes[parent_class].__subclasses__():
            if subclass.__name__ in self.ref_mapping:
                candidates.append(subclass.__name__)
        return candidates

    def build_instance(self, klass, definition, instance_refs, ref_name):
        rels = [r for (r, k) in scan_all_relations(klass)]
        attributes = {k: v for (k, v) in definition.items() if k not in rels}
        return klass(**attributes)

    def build_relation(self, instance, klass_name, definition, instance_refs,
                       relation):
        ref_name = definition[relation]

        def get_instance(candidates):
            instances = []
            for candidate in candidates:
                clean_ref = self.clean_ref(candidate, ref_name)
                related_instance = instance_refs.get(clean_ref)
                if related_instance:
                    instances.append(related_instance)
            return instances

        instances = get_instance([klass_name])
        if not instances:
            instances = get_instance(self.get_relation_candidates(klass_name))

        if not instances and self.auto_load:
            instances = self._load_from_db(
                self.get_relation_candidates(klass_name), ref_name,
                instance_refs)

        if not instances:
            raise Exception('{} not in file or database'.format(ref_name))
        if len(instances) > 1:
            raise Exception('Too many results for {}'.format(ref_name))
        related_instance = instances[0]
        setattr(instance, relation, related_instance)

    def _load_from_db(self, candidates, ref_name, instance_refs):
        values = ref_name.split(self.sep)
        instances = []
        for candidate in candidates:
            keys = self.ref_mapping[candidate].split(self.sep)
            fltr = dict(zip(keys, values))
            qry = self.db.session.query(self.classes[candidate])
            instance = qry.filter_by(**fltr).one_or_none()
            if instance:
                instances.append(instance)
                ref = self.clean_ref(candidate, ref_name)
                instance_refs[ref] = instance
        return instances

    def build_ref(self, klass_name, definition, ref_name):
        names = []
        for name in ref_name.split(self.sep):
            name = name.strip()
            ref_key = definition.get(name, 'None')
            if self.sep not in ref_name:
                ref_key = definition[name]
            names.append(str(ref_key).strip())
        instance_ref = self.sep.join(names)
        return '{}|{}'.format(klass_name, instance_ref)

    def clean_ref(self, klass_name, ref_name):
        names = []
        for name in ref_name.split(self.sep):
            names.append(name.strip())
        instance_ref = self.sep.join(names)
        return '{}|{}'.format(klass_name, instance_ref)


class FastAlchemy:
    def __init__(self, base, session, **kwargs):
        self.Model = base
        self.session = session
        self.class_registry = {}
        self._context_registry = {}
        self.in_context = False
        self.options = Options(**kwargs)

    def _parse_class_definition(self, class_definition):
        inherits_class = (self.Model, )
        class_name = class_definition
        inherits_name = None
        if '|' in class_definition:
            class_name, inherits_name = class_definition.split('|')
            inherits_class = (self.class_registry[inherits_name], )
        return ClassInfo(class_name, inherits_class, inherits_name)

    def _load_file(self, file_or_raw):
        raw = file_or_raw
        if isinstance(file_or_raw, str):
            raw = self.options.file_loader(file_or_raw)
        return raw

    def load(self, filepath):
        raw = self._load_file(filepath)
        self.load_models(raw)
        instances = self.load_instances(raw)
        self.session.add_all(instances.values())
        self.session.commit()

    def load_models(self, file_or_raw):
        field_buider = self.options.field_builder()
        class_builder = self.options.class_builder(self,
                                                   field_buider).build_class
        raw_models = self._load_file(file_or_raw)

        registry = {}
        for class_definition, fields in raw_models.items():
            class_info = self._parse_class_definition(class_definition)
            klass = class_builder(class_info, fields['definition'])
            registry[class_info.class_name] = klass
            self.class_registry[class_info.class_name] = klass
        if self.in_context:
            self._context_registry.update(registry)
        self.create_models(registry.keys())

    def load_instances(self, file_or_raw, auto_load=False, instance_refs=None):
        classes = scan_current_models(self)
        self.class_registry.update(classes)
        raw_instances = self._load_file(file_or_raw)

        # remove notion of subclassing
        raw_instances = {
            self._parse_class_definition(k).class_name: v
            for k, v in raw_instances.items()
        }

        ref_mapping = {}
        for klass_name, definition in raw_instances.items():
            ref_mapping[klass_name.split('|')[0]] = definition['ref']

        loader = self.options.instance_loader(
            self,
            classes,
            ref_mapping,
            self.options.separator,
            auto_load,
        )
        if not instance_refs:
            instance_refs = {}
        instance_refs.update(self._pre_load_existing_instances(raw_instances))

        self._initialisation(raw_instances, instance_refs,
                             loader.load_instance)
        self._initialisation(raw_instances, instance_refs,
                             loader.link_relations)

        return instance_refs

    def _pre_load_existing_instances(self, raw_instances):
        instance_refs = {}
        for class_definition, fields in raw_instances.items():
            physical_refs = []
            for instance in fields.get('instances', []):
                ref = get_ref_from_instance(instance, fields['ref'],
                                            self.options.separator)
                physical_refs.append(ref)

            class_info = self._parse_class_definition(class_definition)
            klass = self.class_registry[class_info.class_name]

            # assemble data to construct filters with.
            fltrs = []
            for rel, rel_klass in scan_all_relations(klass):
                rel_klass = self.class_registry[rel_klass]
                for ref in physical_refs:
                    if rel in ref:
                        definition = get_definition_from_physical_ref(
                            ref[rel], raw_instances[rel_klass.__name__]['ref'],
                            self.options.separator)
                        definition = {
                            k: v
                            for k, v in definition.items()
                            if k in scan_attributes(rel_klass) and v != 'None'
                        }
                        ref[rel] = definition

            # transform filterdata into sqla filters
            fltrs = []
            for ref in physical_refs:
                fltr = []
                for key, value in ref.items():
                    if value == 'None':
                        continue
                    if isinstance(value, dict):
                        if not value:
                            continue
                        fltr.append(getattr(klass, key).has(**value))
                    else:
                        fltr.append(getattr(klass, key) == value)
                fltrs.append(and_(*fltr))
            if not fltrs:
                continue

            # load potentially existing instances
            loaded_instances = self.session.query(klass).filter(
                or_(*fltrs)).all()
            for instance in loaded_instances:
                instance_ref = instance_to_ref(
                    raw_instances, instance, fields['ref'],
                    self.options.separator, self.Model)
                instance_ref = '{}|{}'.format(class_info.class_name,
                                              instance_ref)
                instance_refs[instance_ref] = instance
        return instance_refs

    def _initialisation(self, raw_instances, instance_refs, execute_fn):
        for class_definition, fields in raw_instances.items():
            if not fields.get('instances'):
                continue
            class_info = self._parse_class_definition(class_definition)
            with self.session.no_autoflush:
                execute_fn(class_info, fields['ref'], fields['instances'],
                           instance_refs)

    def __enter__(self):
        self.in_context = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.in_context = False
        self.drop_models(models=self._context_registry.keys())
        self._context_registry = {}

    def get_tables(self, models=None):
        if models is None:
            models = self.class_registry.keys()
        return [
            v.__table__ for (k, v) in self.class_registry.items()
            if k in models
        ]

    def create_models(self, models=None):
        self.execute_for(self.get_tables(models), 'create_all')

    def drop_models(self, models=None):
        self.execute_for(self.get_tables(models), 'drop_all')
        for class_name in models or self.class_registry.keys():
            reg = self.Model._decl_class_registry['_sa_module_registry']
            reg.contents[__name__]._remove_item(class_name)
            self.Model._decl_class_registry.pop(class_name)
            self.Model.metadata.remove(
                self.Model.metadata.tables[class_name.lower()])
            delattr(self, class_name)
            self.class_registry = {}

    def execute_for(self, tables, operation):
        op = getattr(self.Model.metadata, operation)
        op(bind=self.session.bind, tables=tables)


class FlaskFastAlchemy(FastAlchemy):
    def __init__(self, db):
        super().__init__(db.Model, db.session)
