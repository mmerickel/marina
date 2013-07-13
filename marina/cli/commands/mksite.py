from cliff.command import Command
import yaml

class MakeSite(Command):
    def get_description(self):
        return 'Create a new base site configuration.'

    def take_action(self, argv):
        pass
