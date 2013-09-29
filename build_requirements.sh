#! /bin/bash

install()
{
    url=$1
    package=$2
    version=$3

    # download and extract
    cache=$(pwd)/cache
    mkdir $cache
    #pip install --download=$cache $package[$version]
    cd $cache
    wget -q $url/$package-$version.tar.gz
    tar -xzf $package-$version.tar.gz
    cd $package-$version

    # build
    if [[ -n $PREFIX ]]; then
        ./configure --prefix=$PREFIX
    else
        ./configure
    fi
    make

    # install
    make install
}

# dbus-python-1.2.0 requires dbus-1>=1.6 which is currently not available in
# ubuntu version provided by travis. so lets stick with an older version:
install http://dbus.freedesktop.org/releases/dbus-python dbus-python 1.1.1

