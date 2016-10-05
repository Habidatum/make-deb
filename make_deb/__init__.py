import datetime
from os import path, mkdir
from pkg_resources import resource_string
from shutil import rmtree
from subprocess import check_output

from jinja2 import Template

# String setuptools uses to specify None
UNKNOWN = "UNKNOWN"


class DebianConfigurationException(Exception):
    pass


class DebianConfiguration(object):
    '''
    Given a root directory which contains a setup.py file,
    initializes debian configuration files in the debian directory
    '''

    DEBIAN_CONFIGURATION_TEMPLATES = [
        'resources/debian/changelog.j2',
        'resources/debian/compat.j2',
        'resources/debian/control.j2',
        'resources/debian/rules.j2',
    ]

    DEFAULT_CONTEXT = {
        'compat': 9,
    }

    def __init__(self, rootdir):
        self.rootdir = rootdir
        self.context = self.DEFAULT_CONTEXT.copy()
        self.context.update({'date': datetime.datetime.now()})
        self.context.update(self._context_from_setuppy())
        self.context.update(self._context_from_git())

    def _context_from_git(self):
        try:
            out = check_output(['git', 'log', '-1', '--oneline'],
                               cwd=self.rootdir)
            return {"latest_git_commit": out}
        except OSError:
            raise DebianConfigurationException("Please install git")
        except Exception as e:
            raise DebianConfigurationException(
                "Unknown error occurred when invoking git: {}".format(e))

    def _context_from_setuppy(self):
        setuppy_path = path.join(self.rootdir, "setup.py")

        if not path.exists(setuppy_path):
            raise DebianConfigurationException("Failed to find setup.py")

        out = check_output(["python3", path.join(self.rootdir, "setup.py"),
                            "--name", "--version", "--maintainer",
                            "--maintainer-email", "--description"])

        setup_values = out.split('\n')[:-1]
        setup_names = ["name", "version", "maintainer", "maintainer_email",
                       "description"]

        context = {}
        for name, value in zip(setup_names, setup_values):
            if not value or value == UNKNOWN:
                raise DebianConfigurationException(
                    ("We expected to have something at {}, got {}").format(
                        name, value))

            context[name] = value

        return context

    def render(self):
        output_dir = path.join(self.rootdir, "debian")

        if path.exists(output_dir):
            rmtree(output_dir)

        mkdir(output_dir)

        for template in self.DEBIAN_CONFIGURATION_TEMPLATES:
            filename = path.splitext(path.basename(template))[0]

            content = Template(
                resource_string("make_deb", template)).render(self.context)

            with open(path.join(output_dir, filename), "w") as f:
                f.write(content)

        # Need to to trigger separately because filename must change
        trigger_content = Template(
            resource_string("make_deb", "resources/debian/triggers.j2").
            decode('utf-8')
        ).render(self.context)

        trigger_filename = "{}.triggers".format(self.context['name'])
        with open(path.join(output_dir, trigger_filename), "w") as f:
            f.write(trigger_content + "\n")
