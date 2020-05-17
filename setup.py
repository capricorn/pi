import setuptools

setuptools.setup(
    name='predictit',
    version='0.0.1',
    author='capricorn',
    description='Python 3 library for accessing PredictIt REST and Websocket APIs',
    install_requires=['websockets'],
    packages=setuptools.find_packages(),
    python_requires='>=3.7',
)
