import pkg_resources
import sys

import cliff


def main(argv=sys.argv[1:]):
    app = MarinaApp()
    return app.run(argv)


class MarinaApp(cliff.App):
    specifier = 'marina.cli'

    def __init__(self):
        mgr = cliff.CommandManager(self.specifier)
        super(MarinaApp, self).__init__(
            description=(
                'Commands for managing a docker-based deployment '
                'infrastructure.'
            ),
            version=pkg_resources.get_distribution('marina').version,
            command_manager=mgr,
        )
