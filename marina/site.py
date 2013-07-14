from . import defaults
from path import path
import yaml

here = path(__file__).parent


class SiteConfig(object):
    """
    """
    defaults = defaults

    def __init__(self, name, base_dir=path('.'), registry=None, dockers=None, services=None):
        self.path = isinstance(name, path) and name or base_dir / name
        self.name = isinstance(name, path) and str(name.name) or name
        self.dockers = dockers or [self.defaults.docker_url]
        self.services = services or []
        self.registry = registry

    def generate(self):
        self.path.mkdir_p()
        site_data = dict(dockers=self.dockers,
                         name=self.name,
                         services=self.services,
                         registry=self.registry)
        siteyml = self.path / 'site.yml'
        nginx = self.path / 'nginx'
        nginx.mkdir_p()
        siteyml.write_text(yaml.dump(site_data))
