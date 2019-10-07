import os
from collections import OrderedDict

import yaml

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
    for name, klass in db.Model._decl_class_registry.items():
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
