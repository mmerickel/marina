"""

"""
import docker
import yaml
from . import defaults


class ShipIt(object):
    defaults = defaults

    def __init__(self, registry, docker_url):
        docker_url = docker_url or self.defaults.docker_url
        self.docker = docker.Client(docker_url)
        self.registry = registry or self.defaults.registry_url

    def plan(self, services):
        """
        - what container are running
        - are these repos available
        """
        pass

    def execute(self):
        # - validate
        # -
        pass

    @classmethod
    def from_yaml(cls, fp):
        with open(fp) as stream:
            site_data = yaml.load(stream)
        shipper = cls(site_data.pop('registry'), site_data.pop('docker'))
        shipper.execute()
