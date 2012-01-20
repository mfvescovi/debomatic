# Deb-o-Matic
#
# Copyright (C) 2007-2012 Luca Falavigna
#
# Author: Luca Falavigna <dktrkranz@debian.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.

import os
from glob import glob
from re import findall
from urllib2 import Request, urlopen, HTTPError, URLError

from build import Build
from gpg import GPG


class Command():

    def __init__(self, opts, log, pool, commandfile):
        self.log = log
        self.w = self.log.w
        self.opts = opts
        self.pool = pool
        self.configdir = opts.get('default', 'configdir')
        self.packagedir = opts.get('default', 'packagedir')
        self.cmdfile = os.path.join(self.packagedir, commandfile)

    def fetch_dsc(self):
        parms = {}
        conf = {'mirror': ('[^#]?MIRRORSITE="?(.*[^"])"?\n', 'MIRRORSITE'),
                'components': ('[^#]?COMPONENTS="?(.*[^"])"?\n', 'COMPONENTS')}
        try:
            with open(self.originconf, 'r') as fd:
                data = fd.read()
        except IOError:
            self.w(_('Unable to open %s') % originconf)
            return
        for elem in conf.keys():
            try:
                parms[elem] = findall(conf[elem][0], data)[0]
            except IndexError:
                self.data = None
                self.w(_('Please set %(parm)s in %s(conf)s') % \
                       {'parm': conf[elem][0], 'conf': self.originconf})
                return
        for component in parms['components'].split():
            request = Request('%s/pool/%s/%s/%s/%s' %
                              (parms['mirror'], component,
                               findall('^lib\S|^\S', self.package)[0],
                                       self.package, self.dscname))
            try:
                self.data = urlopen(request).read()
                break
            except (HTTPError, URLError):
                self.data = None
                self.w(_('Unable to fetch %s') % \
                       '_'.join((self.package, self.version)))

    def process_command(self):
        self.w(_('Processing %s') % os.path.basename(self.cmdfile))
        gpg = GPG(self.opts, self.cmdfile)
        if gpg.gpg:
            if not gpg.sig:
                os.remove(self.cmdfile)
                self.w(gpg.error)
                return
        with open(self.cmdfile, 'r') as fd:
            cmd = fd.read()
        os.remove(self.cmdfile)
        cmd_rm = findall('\s?rm\s+(.*)', cmd)
        cmd_rebuild = findall('\s?rebuild\s+(\S+)_(\S+) (\S+) ?(\S*)', cmd)
        cmd_porter = findall('\s?porter\s+(\S+)_(\S+) (\S+) (.*)', cmd)
        if cmd_rm:
            self.process_rm(cmd_rm)
        if cmd_porter:
            self.process_porter(cmd_porter)
        if cmd_rebuild:
            self.process_rebuild(cmd_rebuild)

    def process_porter(self, packages):
        for package in packages:
            self.package = package[0]
            self.version = package[1]
            self.dscname = '%s_%s.dsc' % (self.package, self.version)
            self.target = package[2]
            self.debopts = package[3]
            self.originconf = os.path.join(self.configdir, self.target)
            self.fetch_dsc()
            if self.data:
                dsc = os.path.join(self.packagedir, self.dscname)
                with open(dsc, 'w') as fd:
                    fd.write(self.data)
                b = Build(self.opts, self.log, dsc=dsc,
                          distribution=self.target, debopts=self.debopts)
                self.pool.add_task(b.build)

    def process_rebuild(self, packages):
        for package in packages:
            self.package = package[0]
            self.version = package[1]
            self.dscname = '%s_%s.dsc' % (self.package, self.version)
            self.target = package[2]
            self.origin = package[3] if package[3] else package[2]
            self.originconf = os.path.join(self.configdir, self.origin)
            self.fetch_dsc()
            if self.data:
                dsc = os.path.join(self.packagedir, self.dscname)
                with open(dsc, 'w') as fd:
                    fd.write(self.data)
                b = Build(self.opts, self.log, dsc=dsc,
                          distribution=self.target, origin=self.origin)
                self.pool.add_task(b.build)

    def process_rm(self, filesets):
        for files in filesets:
            for pattern in files.split():
                pattern = os.path.basename(pattern)
                for absfile in glob(os.path.join(self.packagedir, pattern)):
                    os.remove(absfile)
