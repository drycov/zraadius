#!/bin/sh
# Create a server key and CSR locally; sign with an external CA.
set -eu
[ "$#" -eq 2 ] || { echo "Usage: $0 OUTPUT_DIR DNS_NAME" >&2; exit 1; }
dir=$1
dns=$2
case "$dns" in ""|*[!a-zA-Z0-9.-]*) echo "Invalid DNS name" >&2; exit 1;; esac
umask 077
mkdir -p "$dir"
[ ! -e "$dir/server.key" ] && [ ! -e "$dir/server.csr" ] || { echo "Refusing to overwrite key or CSR" >&2; exit 1; }
openssl req -new -newkey rsa:3072 -nodes -keyout "$dir/server.key" -out "$dir/server.csr" -subj "/CN=$dns" -addext "subjectAltName=DNS:$dns" -addext "extendedKeyUsage=serverAuth"
