======================================
mugisync: File synchronization utility
======================================

Installing
==========

mugisync can be installed via pip as follows:

::

    pip install mugisync

Using
=====

::

    mugi-sync /path/to/src /path/to/dst -i "*.cpp" -e "moc_*" ".git"
    mugi-sync /src/path/libfoo.dll /dst/path
    mugi-sync /path/to/src /path/to/dst --no-initial-sync

Author
======

Stanislav Doronin <mugisbrows@gmail.com>

License
=======

Mugisync is distributed under the terms of MIT license, check `LICENSE` file.

Contributing
============

If you'd like to contribute, fork the project, make changes, and send a pull
request. Have a look at the surrounding code and please, make yours look
alike :-)