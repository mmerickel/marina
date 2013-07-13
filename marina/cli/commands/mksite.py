from cliff.command import Command
from path import path
import yaml





class MakeSite(Command):
    """
    Create a site directory with all necessary templates
    """
    def get_description(self):
        return 'Create a new base site configuration.'

    def get_parser(self, prog_name):
        parser = super(MakeSite, self).get_parser(prog_name)
        parser.add_argument(
            'site_dir',
            metavar='DEST_FILE',
            required=True,
        )
        return parser

    def take_action(self, args):
        with open(args.config_file, 'wb') as fp:
            fp.write(yaml.dump({}))

