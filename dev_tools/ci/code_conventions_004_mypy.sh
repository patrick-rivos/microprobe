#!/usr/bin/env sh
# Copyright 2011-2021 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Microprobe CI support scripts
#

set -e # Finish right after a non-zero return command

if [ "$WORKSPACE" = "" ]; then
	WORKSPACE=$(pwd)
    export WORKSPACE
fi

# shellcheck source=dev_tools/ci/environment.sh
. "$WORKSPACE/dev_tools/ci/environment.sh"
start_script "$0"

echo "Running mypy version:"
python "$(command -v mypy)" --version

set +e
# shellcheck disable=SC2046
$NICE python "$(command -v mypy)" src/microprobe/code src/microprobe/target targets/generic --exclude targets/generic/wrappers/debug.py --ignore-missing-imports --install-types --non-interactive > "mypy$PYTHON_VERSION.out"
error=$?
set -e

echo "Return code: $error"

error=$(echo "obase=2;$error" | bc | /usr/bin/tail -c 3)
if [ "$error" != "0" ]; then
    echo "Errors found, check mypy$PYTHON_VERSION.out file and fix them"
	exit_error "$0" "mypy$PYTHON_VERSION.out"
fi

# TODO: check other error codes to be more strict
echo "No errors found!"
exit_success "$0"

# vim: set tabstop=4 softtabstop=4 shiftwidth=4 expandtab
