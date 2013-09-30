#! /bin/bash

: ${PREFIX:=/usr}

cache=$(pwd)/cache
mkdir -p $cache

if [[ $TRAVIS_PYTHON_VERSION = 2.* ]]; then
    python2=1
elif [[ -n $TRAVIS_PYTHON_VERSION ]]; then
    python3=1
fi


extract()
{
    filename=$1
    extension=tar.${filename##*.tar.}

    if [[ $extension = "tar.gz" ]]; then
        tar -xzf $filename
    elif [[ $extension = "tar.xz" ]]; then
        tar -xJf $filename
    elif [[ $extension = "tar.bz2" ]]; then
        tar -xjf $filename
    else
        echo 'Unknown extension: ' $filename
        return 1
    fi
}

acquire()
{
    url=$1
    filename=$(basename $url)
    basename=${filename%.tar.*}

    # download and extract
    cd $cache &&
    wget -q $url &&
    extract $filename &&
    cd $basename
}

install()
{
    ./configure --prefix=$PREFIX &&
    make &&
    make install
}

waf_install()
{
    ./waf configure --prefix=$PREFIX &&
    ./waf build &&
    ./waf install
}


# pycairo is a dependency for gobject (one that we actually do not need for
# udiskie):
if [[ -n $python3 ]]; then
    pycairo=http://cairographics.org/releases/pycairo-1.10.0.tar.bz2
else
    pycairo=http://cairographics.org/releases/py2cairo-1.10.0.tar.bz2
fi

# gobject is required for the main loop. this one is really a pain in the
# ass. it feels as if its dependencies outweigh its usefulness by far:
pygobject=http://ftp.acc.umu.se/pub/GNOME/sources/pygobject/2.90/pygobject-2.90.4.tar.xz

# dbus-python-1.2.0 requires dbus-1>=1.6 which is currently not available in
# ubuntu version provided by travis. so lets stick with an older version:
dbus_python=http://dbus.freedesktop.org/releases/dbus-python/dbus-python-1.1.1.tar.gz

# lets try to install everything even if any installation fails:
exitcode=0

# perform installation
#acquire $pycairo && waf_install || exitcode=$?
acquire $pygobject && install || exitcode=$?
acquire $dbus_python && install || exitcode=$?

# signal failure
exit $exitcode

