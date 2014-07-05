import os.path

here = os.path.abspath(os.path.dirname(__file__))

def test_dummy():
    from marina.cli import main
    dummy_path = os.path.join(here, '..', 'examples', 'dummy')
    assert main(['-q', 'build', dummy_path]) == 0
