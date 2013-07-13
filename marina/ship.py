"""

"""
import docker
import yaml


class ShipIt(object):

    docker_default_url = 'http://localhost:4243'
    registry_def_url = 'http://localhost:4244'

    def __init__(self, registry, docker_url):
        docker_url = docker_url or self.docker_default_url
        self.docker = docker.Client(docker_url)
        self.registry = registry or self.registry_def_url

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
