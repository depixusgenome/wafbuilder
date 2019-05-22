#!/usr/bin/env
IR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR/@code@
./@distrib@/bin/python -I @cmdline@ @scriptname@
