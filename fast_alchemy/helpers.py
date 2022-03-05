import os
from collections import OrderedDict

import sqlalchemy
import yaml
from packaging import version

SUPPORTED_FILE_TYPES = ['.yaml', '.yml']


class UnsupportedFileType(Exception):
    pass


# credit to https://stackoverflow.com/
# questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
def ordered_load(stream, Loader=yaml.SafeLoader,
                 object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))

    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    return yaml.load(stream, OrderedLoader)


def scan_current_models(db):
    classes = {}
    for name, klass in get_registered_models(db.Model):
        if isinstance(klass, type) and issubclass(klass, db.Model):
            classes[name] = klass
    return classes


def load_file(filename):
    ext = os.path.splitext(filename)[-1]
    if ext not in SUPPORTED_FILE_TYPES:
        raise UnsupportedFileType(
            '{} not is not a supported file type'.format(ext))
    with open(filename, 'r') as fh:
        return ordered_load(fh)


def get_registered_models_1_3(base_model):
    return base_model._decl_class_registry.items()


def drop_models_1_3(base_model, all_model_names, model_names_to_drop):
    for model_name in model_names_to_drop:
        reg = base_model._decl_class_registry['_sa_module_registry']
        reg.contents["fast_alchemy"]._remove_item(model_name)
        base_model._decl_class_registry.pop(model_name)
        base_model.metadata.remove(
            base_model.metadata.tables[model_name.lower()])


def get_registered_models_1_4(base_model):
    return base_model.registry._class_registry.items()


def drop_models_1_4(base_model, all_model_names, model_names_to_drop):
    to_redeclare = set(all_model_names).difference(model_names_to_drop)

    registry = base_model.registry
    registered_classes = registry._class_registry.items()
    models = {k: v for k, v in registered_classes if k in all_model_names}
    registry.dispose()

    for model_name in to_redeclare:
        registry.map_declaratively(models[model_name])

    for model_name in models:
        base_model.metadata.remove(
            base_model.metadata.tables[model_name.lower()])


get_registered_models = get_registered_models_1_3
drop_models = drop_models_1_3
if version.parse(sqlalchemy.__version__) >= version.parse("1.4.0"):
    get_registered_models = get_registered_models_1_4
    drop_models = drop_models_1_4
