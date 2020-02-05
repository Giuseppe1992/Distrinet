from setuptools import setup
from pathlib import Path
from shutil import copy
from os import system

# create .distrinet/conf.yml configuration in the user home directory
home_dir = Path.home()
conf_dir = home_dir / ".distrinet"
conf_dir.mkdir(0o777, parents=True, exist_ok=True)
copy('conf/conf.yml', str(conf_dir))
copy('conf/general_purpose.json', str(conf_dir))
copy('conf/gros_partial.json', str(conf_dir))
# get the required packages form requiremets.txt
with open('requirements.txt') as f:
    required = f.read().splitlines()
required = list(filter(lambda x: not x.startswith("#") and not x.startswith("git"), required))
print(f"packages required from requirements.txt: {required}")

#install mininet
system("mininet/util/install.sh -a")
#system("install git+git://github.com/Giuseppe1992/mapping_distrinet-1.git")

setup(
    name='Distrinet',
    version='1.2',
    python_requires='>=3.6',
    packages=["mininet"],
    url='https://github.com/Giuseppe1992/Distrinet/tree/master',
    dependency_links=['http://github.com/mininet/mininet/tarball/master#egg=mininet',
                      "https://github.com/Giuseppe1992/mapping_distrinet-1.git"],
    install_requires=required,
    license='MIT',
    author='Giuseppe Di Lena',
    author_email='giuseppedilena92@gmail.com',
    description='Distrinet v.1.2',
    data_files= [(".distrinet", ["conf/conf.yml"])],
    scripts=["mininet/bin/dmn"],
    include_package_data = True,
    zip_safe = True
)
