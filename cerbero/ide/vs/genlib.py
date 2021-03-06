# cerbero - a multi-platform build system for Open Source software
# Copyright (C) 2012 Andoni Morales Alastruey <ylatuya@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import re
import shutil

from cerbero.enums import Architecture, Platform
from cerbero.utils import shell, to_unixpath
from cerbero.utils import messages as m


class GenLib(object):
    '''
    Generates an import library that can be used in Visual Studio from a DLL,
    using 'gendef' to create a .def file and then libtool to create the import
    library (.lib)
    '''

    DLLTOOL_TPL = '$DLLTOOL -d %s -l %s -D %s'
    LIB_TPL = '%s /DEF:%s /OUT:%s /MACHINE:%s'
    filename = 'unknown'

    def create(self, libname, dllpath, platform, target_arch, outputdir):
        # foo.lib must not start with 'lib'
        if libname.startswith('lib'):
            self.filename = libname[3:] + '.lib'
        else:
            self.filename = libname + '.lib'

        bindir, dllname = os.path.split(dllpath)

        # Create the .def file
        shell.call('gendef %s' % dllpath, outputdir)

        defname = dllname.replace('.dll', '.def')

        # Create the import library
        lib_path, paths = self._get_lib_exe_path(target_arch, platform)

        # Prefer LIB.exe over dlltool:
        # http://sourceware.org/bugzilla/show_bug.cgi?id=12633
        if lib_path is not None:
            # Spaces msys and shell are a beautiful combination
            lib_path = to_unixpath(lib_path)
            lib_path = lib_path.replace('\\', '/')
            lib_path = lib_path.replace('(', '\\\(').replace(')', '\\\)')
            lib_path = lib_path.replace(' ', '\\\\ ')
            if target_arch == Architecture.X86:
                arch = 'x86'
            else:
                arch = 'x64'
            old_path = os.environ['PATH']
            os.environ['PATH'] = paths + ';' + old_path
            shell.call(self.LIB_TPL % (lib_path, defname, self.filename, arch),
                       outputdir)
            os.environ['PATH'] = old_path
        else:
            m.warning("Using dlltool instead of lib.exe! Resulting .lib files"
                " will have problems with Visual Studio, see "
                " http://sourceware.org/bugzilla/show_bug.cgi?id=12633")
            shell.call(self.DLLTOOL_TPL % (defname, self.filename, dllname),
                       outputdir)
        return os.path.join(outputdir, self.filename)

    def _get_lib_exe_path(self, target_arch, platform):
        # No Visual Studio tools while cross-compiling
        if platform != Platform.WINDOWS:
            return None, None
        from cerbero.ide.vs.env import get_msvc_env
        msvc_env = get_msvc_env('x86', target_arch)
        paths = msvc_env['PATH']
        return shutil.which('lib', path=paths), paths

class GenGnuLib(GenLib):
    '''
    Generates an import library (libfoo.dll.a; not foo.lib) that is in a format
    that allows GNU ld to resolve all symbols exported by a DLL created by MSVC.

    Usually everything works fine even if you pass a .lib import library created
    by MSVC to GNU GCC/LD, but it won't find any exported DATA (variable)
    symbols from the import library. It can find them if you pass it the DLL
    directly, but that's a terrible idea and breaks how library searching works,
    so we create a GNU-compatible import library which will always work.
    '''

    def create(self, libname, dllpath, platform, target_arch, outputdir):
        # libfoo.dll.a must start with 'lib'
        if libname.startswith('lib'):
            self.filename = libname + '.dll.a'
        else:
            self.filename = 'lib{0}.dll.a'.format(libname)
        dllname = os.path.basename(dllpath)
        # Create the .def file
        shell.call('gendef ' + dllpath, outputdir)
        defname = dllname.replace('.dll', '.def')
        shell.call(self.DLLTOOL_TPL % (defname, self.filename, dllname), outputdir)
        return os.path.join(outputdir, self.filename)
