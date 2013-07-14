import pkg_resources
import sys

from cliff.app import App
from cliff.commandmanager import CommandManager

from .commands.mksite import MakeSite
from .commands.info import Info
from .commands.ship import Ship


def main(argv=sys.argv[1:]):
    app = MarinaApp()
    return app.run(argv)


class MarinaApp(App):
    specifier = 'marina.cli'

    def __init__(self):
        mgr = CommandManager(self.specifier)
        super(MarinaApp, self).__init__(
            description=(
                'Commands for managing a docker-based deployment '
                'infrastructure.'
            ),
            version=pkg_resources.get_distribution('marina').version,
            command_manager=mgr,
        )
        commands = {
            'mksite': MakeSite,
            'ship': Ship,
            'info': Info,
        }
        for k, v in commands.items():
            mgr.add_command(k, v)
