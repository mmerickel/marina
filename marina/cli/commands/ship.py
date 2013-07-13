from cliff.command import Command


class Ship(Command):
    def get_description(self):
        return 'Fuck it. Ship it.'

    def get_parser(self, prog_name):
        parser = super(Ship, self).get_parser(prog_name)
        parser.add_argument(
            'config_file',
            metavar='DEST_FILE',
            default='site.yml',
        )
        return parser

    def take_action(self, args):
        """
        """
        pass
