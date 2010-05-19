from distutils.core import setup

setup(
    name='udiskie',
    version='0.3.0',
    description='Removable disk automounter for udisks',
    author='Byron Clark',
    author_email='byron@theclarkfamily.name',
    url='http://bitbucket.org/byronclark/udiskie',
    license='MIT',
    packages=[
        'udiskie',
    ],
    scripts=[
        'bin/udiskie',
        'bin/udiskie-umount',
    ],
)
