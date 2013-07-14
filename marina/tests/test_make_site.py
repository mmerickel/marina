from path import path
import tempfile
import unittest
import yaml


class TestSiteConfig(unittest.TestCase):
    """
    """
    def setUp(self):
        self.tmpdir = path(tempfile.mkdtemp())

    def makeone(self, name):
        from marina.site import SiteConfig
        return SiteConfig(self.tmpdir / name)

    def test_siteconfig_gen(self):
        name = 'test1'
        sc = self.makeone(name)
        sc.generate()

        site = sc.path 
        assert 'site.yml' in set(x.name for x  in site.files())
        assert 'nginx' in set(x.name for x  in site.dirs())
        siteyml = site / 'site.yml'
        assert siteyml.parent.exists()
        assert siteyml.text(), siteyml.text()
        with open(siteyml) as stream:
            data = yaml.load(stream)

        keys = set(('registry', 'dockers', 'services', 'name'))
        assert set(data.keys()) == keys, keys.difference(set(data.keys()))

    def tearDown(self):
        self.tmpdir.rmtree_p()
