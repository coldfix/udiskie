Translations
------------

Translations by users are always welcome. The corresponding files are in the
`lang`_ subfolder. In order to create a new translation, find out the locale
name for your language, e.g. ``es_ES`` for Spanish, and create a translation
file in the ``lang`` folder as follows::

    cd lang
    make es_ES.po

or simply copy the `udiskie.pot`_ to a ``.po`` file with the name of the
target locale and start editing. It's also best to fill in your name and email
address.

The translations may become outdated as udiskie changes. If you notice an
outdated translation, please edit the corresponding ``.po`` file in submit a
patch, even for very small changes.

In order to test udiskie with your locally edited translation files, type
(still from the ``lang`` folder)::

    export TEXTDOMAINDIR=$PWD/../build/locale
    export LANG=es_ES.UTF-8

    make mo

    udiskie

.. _lang: https://github.com/coldfix/udiskie/tree/master/lang
.. _udiskie.pot: https://raw.githubusercontent.com/coldfix/udiskie/master/lang/udiskie.pot
