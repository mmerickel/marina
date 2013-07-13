"""
Generate a site folder and templates
"""
from path import path
from . import defaults
import yaml

here = path(__file__).parent

class SiteConfig(object):
    defaults = defaults

    def __init__(self, fp=path('.'), registry=None, dockers=None, services=None):
        self.name = str(fp.name)
        self.path = fp
        self.dockers = dockers or [self.defaults.docker_url]
        self.services = services or []
        self.registry = registry

    def generate(self):
        site_data = dict(dockers=self.dockers,
                         name=self.name,
                         services=self.services,
                         registry=self.registry)
        siteyml = self.path / 'site.yml'
        nginx = self.path / 'nginx'
        nginx.mkdir_p()
        siteyml.write_text(yaml.dump(site_data))
