# Transifex Pull

## Installation

    $ git clone *
    $ cd tx_pull
    $ virtualenv env
    $ . env/bin/activate
    $ python setup.py install

## Usage

Retrieve the transifex slug name. It's the code of your project. You'll find this code in the url of your project.

    $ tx_pull

## Developers

As a developer, you want to launch the scripts without installing the
egg.

    $ git clone *
    $ cd tx_pull
    $ virtualenv env
    $ . env/bin/activate
    $ pip install -e .
