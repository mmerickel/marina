import tarfile
import tempfile

def tar(path):
    f = tempfile.NamedTemporaryFile()
    t = tarfile.open(mode='w', fileobj=f)
    t.add(path, arcname='.')
    t.close()
    f.seek(0)
    return f
