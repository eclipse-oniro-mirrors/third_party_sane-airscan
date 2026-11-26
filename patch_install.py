#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2025 Huawei Device Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Applies the OpenHarmony patch series to a private source copy.
 
The patched files are created under the build output directory (see
--dest-dir), so the source checkout stays pristine and every build
product stays inside out/. All action inputs (the patch series, the
compiled sources and the patch-only files) are declared statically in
BUILD.gn, so no depfile is needed.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PATCHES = [
    'oh-transplant.patch',
    'oh-fix-subtraction-underflow.patch',
    'oh-fix-heap-overflow-dimension.patch',
    'oh-fix-resolution-overflow.patch',
    'oh-fix-http-hdr-params-parse-null-deref.patch',
    'oh-fix-http-body-limit.patch',
    'oh-fix-empty-source-caps.patch',
    'oh-fix-eloop-uv-run-mutex-serialization.patch',
    'oh-fix-skip-branch-buffer-capacity.patch',
    'oh-escl-https-tofu.patch',
]


def parse_args():
    parser = argparse.ArgumentParser(
        description='Build a patched copy of the sane-airscan sources.')
    parser.add_argument('--source-dir', required=True,
                        help='pristine sane-airscan checkout, relative to '
                             'the build directory')
    parser.add_argument('--dest-dir', required=True,
                        help='location of the patched copy inside the '
                             'build output directory')
    parser.add_argument('--file', action='append', required=True,
                        help='source file (relative to --source-dir) to '
                             'copy and patch; repeatable')
    return parser.parse_args()


def _patch_target_files(source):
    """Returns the files modified by the patch series (patch headers)."""
    targets = set()
    for name in PATCHES:
        text = (source / 'patches' / name).read_text(encoding='utf-8',
                                                     errors='surrogateescape')
        for line in text.splitlines():
            if line.startswith(('--- a/', '+++ b/')):
                target = line[6:].split('\t')[0]
                if target.startswith('/') or '..' in Path(target).parts:
                    raise ValueError('unsafe patch target: %s' % target)
                targets.add(target)
    return sorted(targets)


def _copy_sources(source, dest, files):
    """Copies the file list from the checkout into the dest copy.

    Timestamps are refreshed to the current time on purpose: ninja expects
    an action's outputs to be newer than its inputs after a rerun, so
    preserving source mtimes would leave the edge permanently dirty.
    """
    for name in files:
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
        os.utime(target, None)


def _apply_one_patch(source, dest, name):
    """Applies one patch file to the dest copy."""
    command = ['patch', '--batch', '--forward', '-p1', '--fuzz=0',
               '--no-backup-if-mismatch',
               '-i', str(source / 'patches' / name), '-d', str(dest)]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('%s failed (is the checkout already patched? '
                           'restore it with git):\n%s'
                           % (name, result.stdout))


def apply_patches(source, dest, files):
    """Rebuilds the patched copy from scratch on every run.

    The dest directory lives inside the build output directory, so it
    can be wiped safely. Besides the files requested by the build (see
    --file), every file touched by the patch series is copied too, so
    patches may also target files the library does not compile. A
    failed run leaves no half-patched state behind: the next run
    starts from the pristine checkout again.
    """
    all_files = sorted(set(files) | set(_patch_target_files(source)))
    shutil.rmtree(dest, ignore_errors=True)
    _copy_sources(source, dest, all_files)
    for name in PATCHES:
        _apply_one_patch(source, dest, name)


def main():
    args = parse_args()
    source = Path(os.path.abspath(args.source_dir))
    dest = Path(os.path.abspath(args.dest_dir))

    apply_patches(source, dest, args.file)
    return 0


if __name__ == '__main__':
    sys.exit(main())
