#!/bin/bash

prompt_yn() {
    read -p "$1 (yN) " yn;
    case $yn in
        [Yy]* ) return 0;;
        * ) return 1;;
    esac
}

require() {
    if ! $@; then
        echo "Error running $@, exiting...";
        exit 1;
    fi
}

GO="$(which go)"
BUILDFLAGS=""
PUPPYREPO="https://github.com/roglew/puppy.git"
PUPPYVERSION="tags/0.2.3"

INSTALLDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TMPGOPATH="$INSTALLDIR/gopath"
DATADIR="$HOME/.pappy"
VIRTUALENVNAME="pappyenv"

while getopts "g:f:r:dh" opt; do
    case $opt in
        g)
            GO="$OPTARG"
            ;;
        f)
            BUILDFLAGS="${OPTARG}"
            ;;
        r)
            PUPPYREPO="${OPTARG}"
            DEV="yes"
            ;;
        d)
            DEV="yes"
            ;;
        h)
            echo -e "Build script flags:"
            echo -e "-g [path to go]\tUse specific go binary to compile puppy"
            echo -e "-f [arguments]\tArguments to pass to \"go build\". ie -f \"-ldflags -s\""
            echo -e "-r [git repository link]\t download puppy from an alternate repository"
            echo -e "-d\tinstall puppy in development mode by using \"pip install -e\" to install puppy"
            echo -e "-h\tprint this help message"
            echo -e ""
            exit 0;
            ;;

        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1;
            ;;
    esac
done

if ! type "pip" > /dev/null; then
    if ! type "easy_install" > /dev/null; then
        echo "easy_install not available. Please install easy_install then try again."
        exit 1;
    fi

    if prompt_yn "Installation requires pip. Install pip using \"sudo easy_install pup\"?"; then
        require sudo easy_install pip;
    else
        echo "Please install pip and try the installation again"
        exit 1;
    fi
fi

cd /tmp
if python -c "import pappyproxy" &> /dev/null; then
    echo "An earlier version of pappy appears to be installed. Please remove it and try installation again."
    echo "This can likely be done by running \"pip uninstall pappyproxy\""
    exit 1;
fi
cd "$INSTALLDIR"

# Set up fake gopath
if [ -z "$GOPATH" ]; then
    echo "No GOPATH detected, creating temporary GOPATH at $TMPGOPATH";
    export GOPATH="$TMPGOPATH";
fi
require mkdir -p "$GOPATH/src"

# Clone the repo
REPODIR="$GOPATH/src/puppy";
if [ ! -d "$REPODIR" ]; then
    # Clone the repo if it doesn't exist
    require mkdir -p "$REPODIR";
    echo git clone "$PUPPYREPO" "$REPODIR";
    require git clone "$PUPPYREPO" "$REPODIR";
fi

# Check out the correct version
cd "$REPODIR";
if [ $DEV ] || [ $REPODIR ]; then
    # If it's development, get the most recent version of puppy
    require git pull;
else
    # if it's not development, get the specified version
    require git checkout "$PUPPYVERSION";
fi
cd "$INSTALLDIR"

# Get dependencies
cd "$REPODIR";
echo "Getting puppy dependencies..."
require "$GO" get ./...;

# Build puppy into the data dir
echo "Building puppy into $DATADIR/puppy...";
require mkdir -p "$DATADIR";
require "$GO" build -o "$DATADIR"/puppy $BUILDFLAGS "puppy/cmd/main";

# Clear out old .pyc files
require find "$INSTALLDIR/pappyproxy" -iname "*.pyc" -exec rm -f {} \;

# Set up the virtual environment
if ! type "virtualenv" > /dev/null; then
    if prompt_yn "\"virtualenv\" not installed. Install using pip?"; then
        require sudo pip install virtualenv
    else
        exit 1;
    fi
fi

VENVDIR="$DATADIR/venv";
require mkdir -p "$VENVDIR";
require virtualenv -p "$(which python3)" "$VENVDIR";
cd "$VENVDIR";
require source bin/activate;
cd "$INSTALLDIR";

if [ -z $DEV ]; then
    require pip install -e .
else
    require pip install .
fi

echo -e "#!/bin/bash\nsource \"$VENVDIR/bin/activate\";\npappy \$@;\n" > start
chmod +x start;

echo ""
echo "Pappy installed. Run pappy by executing the generated \"start\" script."
