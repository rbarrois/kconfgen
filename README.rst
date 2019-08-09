kconfgen
========

.. image:: https://secure.travis-ci.org/rbarrois/kconfgen.svg?branch=master
    :target: https://travis-ci.org/rbarrois/kconfgen/

.. image:: https://img.shields.io/pypi/v/kconfgen.svg
    :target: https://kconfgen.readthedocs.io/en/latest/changelog.html
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/pyversions/kconfgen.svg
    :target: https://pypi.org/project/kconfgen/
    :alt: Supported Python versions

.. image:: https://img.shields.io/pypi/wheel/kconfgen.svg
    :target: https://pypi.org/project/kconfgen/
    :alt: Wheel status

.. image:: https://img.shields.io/pypi/l/kconfgen.svg
    :target: https://pypi.org/project/kconfgen/
    :alt: License

``kconfgen`` is a tool to manage Linux kernel configuration files.

It enables users to:

* Assemble kernel configuration files from fragments;
* Ensure that only minimal lists of flags are kept in version control;
* Split a single kernel configuration file in fragments by topic.


Usage:
------

``kconfgen merge``
""""""""""""""""""

Assemble a ``.config`` file from a set of (minimal) definitions

.. code-block:: sh

  kconfgen merge \
    --kernel=/usr/src/linux-4.19.57 --arch=x86 \
    defconfig.net defconfig.crypto defconfig.laptop > .config


It is also possible to generate a ``defconfig`` file, which contains only the minimal set of flags
to get to the provided ``.config`` file:

.. code-block:: sh

  kconfgen merge \
    --kernel=/usr/src/linux-4.19.57 --arch=x86 \
    --minimal \
    defconfig.net defconfig.crypto defconfig.laptop > some_host.defconfig



``kconfgen split``
""""""""""""""""""

Split a ``.config`` file into a set of minimal definitions, based on their sections:

.. code-block:: sh

  kconfgen split \
    --kernel=/usr/src/linux-4.19.57 --arch=x86 \
    --sections="net crypto fs" \
    ./fragments/ < ./.config

  ls fragments/
    defconfig.net
    defconfig.crypto
    defconfig.fs
    defconfig

It is also possible to split by maximal section size:

.. code-block:: sh

  kconfgen split \
    --kernel=/usr/src/linux-4.19.57 --arch=x86 \
    --max-symbols=20 \
    ./fragments/ < ./.config

  ls fragments/
    defconfig.net
    defconfig.net_netfilter
    defconfig.crypto
    defconfig.drivers
    defconfig

``kconfgen assemble``
"""""""""""""""""""""

Assemble a ``defconfig`` file for a specific profile:

.. code-block:: sh

  kconfgen assemble \
    --kernel=/usr/src/linux-4.19.57 \
    --profiles=profiles.toml \
    some-profile > .config

The list of profiles and the ``defconfig`` files to use for them is listed in a toml file:

.. code-block:: toml

  [ profile.example ]
  arch = x86
  include = [ "core", "server" ]
  extras = [ "defconfig.example", "defconfig.wifi_intel" ]

  [ include.core ]
  files = [ "defconfig.crypto", "defconfig.fs" ]

  [ include.server ]
  files = [ "defconfig.net", "defconfig.net_netfilter" ]
