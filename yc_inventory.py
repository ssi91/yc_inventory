#!/Users/ssi/yc_dynamic_inventory/bin/python
import json
import os

import yaml
import yandexcloud
from yaml import Loader
from yandex.cloud.compute.v1.instance_service_pb2 import ListInstancesRequest
from yandex.cloud.compute.v1.instance_service_pb2_grpc import InstanceServiceStub


def find_by_labels(instances, labels):
    if len(labels) == 0:
        return instances

    res = []
    for inst in instances:
        for k, v in labels.items():
            lbls = v
            if isinstance(v, str):
                lbls = [v]
            if k in inst.labels and any(inst.labels[k] == lbl for lbl in lbls):
                res.append(inst)
    return res


class ConfigIsNotExists(Exception):
    def __init__(self, msg, find_paths, config_name):
        super().__init__(msg)
        self.find_paths = find_paths
        self.config_name = config_name


class ValidationError(Exception):
    pass


class ConfigFinder:
    DEFAULT_PATHS = (
        './',
        '~/.yandex_cloud',
    )

    CONFIG_NAME = 'config.yaml'

    @classmethod
    def __get_path(cls):
        for path in cls.DEFAULT_PATHS:
            found_path = os.path.join(path, cls.CONFIG_NAME)
            if not os.path.exists(found_path):
                continue
            return found_path
        raise ConfigIsNotExists("Config wasn't found", cls.DEFAULT_PATHS, cls.CONFIG_NAME)

    @classmethod
    def stream(cls):
        config_path = cls.__get_path()
        with open(config_path) as f:
            stream = f.read()
        return stream


class ServiceAccount(dict):
    def __init__(self, path=None, stream=None):
        if path is not None and stream is not None:
            raise ValueError("Parameter conflict: only one of `path` or `stream` must be set.")
        if path is None and stream is None:
            raise ValueError("Parameter error: one of `path` or `stream` must be set.")
        if path is not None:
            with open(path) as f:
                stream = f.read()
        self.__parsed_data = self._set_from_stream(stream)

    def __getitem__(self, item):
        return self.__parsed_data[item]

    @classmethod
    def _set_from_stream(cls, stream):
        # TODO: validate?
        return json.loads(stream)

    def get(self, k):
        return self.__parsed_data.get(k)


class Config:
    _FINDER = ConfigFinder
    _SERVICE_ACCOUNT = ServiceAccount

    _REQUIRED_FIELDS = (
        'folderId',
        'keyFile',
        'tags',
    )

    def __init__(self):
        self._finder_instance = self._FINDER()
        self.__stream = self._finder_instance.stream()
        self.__parsed_config = yaml.load(self.__stream, Loader=Loader)

        self._service_account = None

        self._validate()

    def __getitem__(self, item):
        return self.__parsed_config.get(item)

    def _validate(self):
        try:
            self._check_required_field()
        except KeyError as k:
            raise ValidationError("Key %s is required." % k)
        if not self._is_sa_key_file_exist():
            raise ValidationError(
                "Service Account credentials was not found. Path: %s" % self.__parsed_config['keyFile']
            )

    def _check_required_field(self):
        _ = all(key in self.__parsed_config for key in self._REQUIRED_FIELDS)

    def _is_sa_key_file_exist(self):
        return os.path.exists(self.__parsed_config['keyFile'])

    @property
    def service_account(self):
        if self._service_account is None:
            self._service_account = self._SERVICE_ACCOUNT(self.__parsed_config['keyFile'])
        return self._service_account


config = Config()


def generate_inventory(conf):
    sdk = yandexcloud.SDK(service_account_key=conf.service_account)

    c = sdk.client(InstanceServiceStub)

    l = c.List(ListInstancesRequest(
        folder_id=conf['folderId']
    ))

    tags = [k for k in conf['tags'].keys()]

    tag_hosts_map = {
        tag: [
            i.network_interfaces[0].primary_v4_address.one_to_one_nat.address for i in find_by_labels(
                l.instances, {'tags': [tag]}
            )
        ] for tag in conf['tags'].keys()
    }

    def set_host_as_value(var_hosts):
        if isinstance(var_hosts, list):
            return [set_host_as_value(host) for host in var_hosts]
        if any(var_hosts == tag_name for tag_name in tags):
            return tag_hosts_map[var_hosts]
        if var_hosts.find('[') != -1 and var_hosts.find(']') == len(var_hosts) - 1:
            tag_name, index = var_hosts.split('[')
            index = int(index[:-1])
            if len(tag_hosts_map[tag_name]) <= index:
                # FIXME: it seems like an error in the config
                return []
            return tag_hosts_map[tag_name][index]

    def extract_var(var):
        if 'value' in var:
            return var['value']
        return set_host_as_value(var['hosts'])

    # extract vars
    tag_host_vars_map = {}
    for tag in tags:
        if 'vars' not in config['tags'][tag] or config['tags'][tag]['vars'] is None:
            continue
        tag_host_vars_map[tag] = {
            var_name: extract_var(config['tags'][tag]['vars'][var_name]) for var_name in config['tags'][tag]['vars']
        }

    result_inventory = {}
    for tag, hosts in tag_hosts_map.items():
        hosts_name = tag
        if 'hostsName' in config['tags'][tag]:
            hosts_name = config['tags'][tag]['hostsName']
        result_inventory[hosts_name] = {
            'hosts': hosts
        }
        if tag in tag_host_vars_map:
            result_inventory[hosts_name]['vars'] = tag_host_vars_map[tag]
    return result_inventory


inventory = generate_inventory(config)

print(json.dumps(inventory))
