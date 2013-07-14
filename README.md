## Setup a Standalone Vagrant box

There is a standard deployment configuration in `ansible`.

- Install ansible into the system path or through a virtualenv:

  ```bash
  virtualenv env
  env/bin/pip install ansible
  . env/bin/activate
  ```

- Start the vagrant box:

  ```bash
  vagrant up
  ```
