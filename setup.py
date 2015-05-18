from distutils.core import setup
setup(name='csiro_workspace',
      version='0.1',
      description='Workspace Python Module',
      author='CSIRO',
      author_email='workspace@csiro.au',
      url='http://research.csiro.au/workspace',
      packages=['csiro_workspace'],
      package_data={'csiro_workspace': ['workspace.cfg']}
)

