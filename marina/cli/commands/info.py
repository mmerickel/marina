from cliff.command import Command
import docker


class Info(Command):
    def get_description(self):
        return 'Query the state of the system deployment.'

    def get_parser(self, prog_name):
        parser = super(Info, self).get_parser(prog_name)
        parser.add_argument(
            'config_file',
            metavar='DEST_FILE',
            default='site.yml',
        )
        return parser

    def take_action(self, args):
        client = docker.Client('http://localhost:4243')
        import pdb; pdb.set_trace()
