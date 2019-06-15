from setuptools import setup

import autoversion

details = {
	'name': autoversion.__name__,
	'description': autoversion.__doc__,
	'version': str(autoversion.get_version()),
	'author': 'David Finn',
	'author_email': 'dsfinn@gmail.com',
	'packages': [autoversion.__package__],
}

setup(**details)
