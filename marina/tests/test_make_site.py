from path import path
import tempfile
import unittest
import yaml


class TestSiteConfig(unittest.TestCase):
    """
    """
    def setUp(self):
        self.tmpdir = path(tempfile.mkdtemp())

    def makeone(self):
        from marina.site import SiteConfig
        return SiteConfig(self.tmpdir)

    def test_siteconfig_gen(self):
        sc = self.makeone()
        sc.generate()
        assert 'site.yml' in set(x.name for x  in self.tmpdir.files())
        assert 'nginx' in set(x.name for x  in self.tmpdir.dirs())
        siteyml = sc.path / 'site.yml'
        assert siteyml.text(), siteyml.text()
        with open(siteyml) as stream:
            data = yaml.load(stream)
        keys = set(('registry', 'dockers', 'services', 'name'))
        assert set(data.keys()) == keys, keys.difference(set(data.keys()))


    def tearDown(self):
        self.tmpdir.rmtree_p()
