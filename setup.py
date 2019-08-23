from setuptools import setup, find_packages

setup(
    name='Distrinet',
    version='1.1',
    python_requires='>=3.6',
    packages=find_packages(exclude=["src"]),
    url='https://github.com/Giuseppe1992/Distrinet/tree/parallel-execution',
    dependency_links=['http://github.com/mininet/mininet/tarball/master#egg=mininet',
                      "https://github.com/Giuseppe1992/mapping_distrinet.git"],
    install_requires=[
    ],
    license='MIT',
    author='Giuseppe Di Lena',
    author_email='giuseppedilena92@gmail.com',
    description='Distrinet v.1.1',
    data_files= [("~/.distrinet",["conf/conf.yml"])]

)
