#!/bin/bash

python -m pproxy -l socks5://:${PPROXY_PORT:-9017}/ -v
