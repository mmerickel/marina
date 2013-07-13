from cliff.command import Command
import yaml

class MakeSite(Command):
    def get_description(self):
        return 'Create a new base site configuration.'

    def get_parser(self, prog_name):
        parser = super(MakeSite, self).get_parser(prog_name)
        parser.add_argument(
            'config_file',
            metavar='DEST_FILE',
            default='site.yml',
        )
        return parser

    def take_action(self, args):
        with open(args.config_file, 'wb') as fp:
            fp.write(yaml.dump({}))
