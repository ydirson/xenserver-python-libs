# -*- coding: iso-8859-15 -*-

import sys
import os
import shutil
import tempfile
import StringIO
from hashlib import md5
import errno

import unittest
import cpiofile

from test import test_support

# Check for our compression modules.
try:
    import gzip
    gzip.GzipFile
except (ImportError, AttributeError):
    gzip = None
try:
    import bz2
except ImportError:
    bz2 = None

def md5sum(data):
    return md5(data).hexdigest()

def path(path):
    return test_support.findfile(path)

TEMPDIR = os.path.join(tempfile.gettempdir(), "test_cpiofile_tmp")
cpioname = path("testcpio.cpio")
gzipname = os.path.join(TEMPDIR, "testcpio.cpio.gz")
bz2name = os.path.join(TEMPDIR, "testcpio.cpio.bz2")
tmpname = os.path.join(TEMPDIR, "tmp.cpio")

md5_regtype = "65f477c818ad9e15f7feab0c6d37742f"
md5_sparse = "a54fbc4ca4f4399a90e1b27164012fc6"


class ReadTest(unittest.TestCase):

    cpioname = cpioname
    mode = "r:"

    def setUp(self):
        self.cpio = cpiofile.open(self.cpioname, mode=self.mode, encoding="iso8859-1")

    def tearDown(self):
        self.cpio.close()


class UstarReadTest(ReadTest):

    def test_fileobj_regular_file(self):
        tarinfo = self.tar.getmember("ustar/regtype")
        fobj = self.tar.extractfile(tarinfo)
        data = fobj.read()
        self.assert_((len(data), md5sum(data)) == (tarinfo.size, md5_regtype),
                "regular file extraction failed")

    def test_fileobj_readlines(self):
        self.tar.extract("ustar/regtype", TEMPDIR)
        tarinfo = self.tar.getmember("ustar/regtype")
        fobj1 = open(os.path.join(TEMPDIR, "ustar/regtype"), "rU")
        fobj2 = self.tar.extractfile(tarinfo)

        lines1 = fobj1.readlines()
        lines2 = fobj2.readlines()
        self.assert_(lines1 == lines2,
                "fileobj.readlines() failed")
        self.assert_(len(lines2) == 114,
                "fileobj.readlines() failed")
        self.assert_(lines2[83] == \
                "I will gladly admit that Python is not the fastest running scripting language.\n",
                "fileobj.readlines() failed")

    def test_fileobj_iter(self):
        self.tar.extract("ustar/regtype", TEMPDIR)
        tarinfo = self.tar.getmember("ustar/regtype")
        fobj1 = open(os.path.join(TEMPDIR, "ustar/regtype"), "rU")
        fobj2 = self.tar.extractfile(tarinfo)
        lines1 = fobj1.readlines()
        lines2 = [line for line in fobj2]
        self.assert_(lines1 == lines2,
                     "fileobj.__iter__() failed")

    def test_fileobj_seek(self):
        self.tar.extract("ustar/regtype", TEMPDIR)
        fobj = open(os.path.join(TEMPDIR, "ustar/regtype"), "rb")
        data = fobj.read()
        fobj.close()

        tarinfo = self.tar.getmember("ustar/regtype")
        fobj = self.tar.extractfile(tarinfo)

        text = fobj.read()
        fobj.seek(0)
        self.assert_(0 == fobj.tell(),
                     "seek() to file's start failed")
        fobj.seek(2048, 0)
        self.assert_(2048 == fobj.tell(),
                     "seek() to absolute position failed")
        fobj.seek(-1024, 1)
        self.assert_(1024 == fobj.tell(),
                     "seek() to negative relative position failed")
        fobj.seek(1024, 1)
        self.assert_(2048 == fobj.tell(),
                     "seek() to positive relative position failed")
        s = fobj.read(10)
        self.assert_(s == data[2048:2058],
                     "read() after seek failed")
        fobj.seek(0, 2)
        self.assert_(tarinfo.size == fobj.tell(),
                     "seek() to file's end failed")
        self.assert_(fobj.read() == "",
                     "read() at file's end did not return empty string")
        fobj.seek(-tarinfo.size, 2)
        self.assert_(0 == fobj.tell(),
                     "relative seek() to file's start failed")
        fobj.seek(512)
        s1 = fobj.readlines()
        fobj.seek(512)
        s2 = fobj.readlines()
        self.assert_(s1 == s2,
                     "readlines() after seek failed")
        fobj.seek(0)
        self.assert_(len(fobj.readline()) == fobj.tell(),
                     "tell() after readline() failed")
        fobj.seek(512)
        self.assert_(len(fobj.readline()) + 512 == fobj.tell(),
                     "tell() after seek() and readline() failed")
        fobj.seek(0)
        line = fobj.readline()
        self.assert_(fobj.read() == data[len(line):],
                     "read() after readline() failed")
        fobj.close()


class MiscReadTest(ReadTest):

    def test_no_filename(self):
        fobj = open(self.cpioname, "rb")
        cpio = cpiofile.open(fileobj=fobj, mode=self.mode)
        self.assertEqual(cpio.name, os.path.abspath(fobj.name))

    def test_fail_comp(self):
        # For Gzip and Bz2 Tests: fail with a ReadError on an uncompressed file.
        if self.mode == "r:":
            return
        self.assertRaises(cpiofile.ReadError, cpiofile.open, cpioname, self.mode)
        fobj = open(cpioname, "rb")
        self.assertRaises(cpiofile.ReadError, cpiofile.open, fileobj=fobj, mode=self.mode)

    def test_v7_dirtype(self):
        # Test old style dirtype member (bug #1336623):
        # Old V7 tars create directory members using an AREGTYPE
        # header with a "/" appended to the filename field.
        tarinfo = self.tar.getmember("misc/dirtype-old-v7")
        self.assert_(tarinfo.type == tarfile.DIRTYPE,
                "v7 dirtype failed")

    def test_check_members(self):
        for cpioinfo in self.cpio:
            self.assert_(int(cpioinfo.mtime) == 07606136617,
                    "wrong mtime for %s" % cpioinfo.name)
            if not cpioinfo.name.startswith("ustar/"):
                continue
            self.assert_(cpioinfo.uname == "cpiofile",
                    "wrong uname for %s" % cpioinfo.name)

    def test_find_members(self):
        self.assert_(self.cpio.getmembers()[-1].name == "misc/eof",
                "could not find all members")

    def test_extract_hardlink(self):
        # Test hardlink extraction (e.g. bug #857297).
        cpio = cpiofile.open(cpioname, errorlevel=1, encoding="iso8859-1")

        cpio.extract("ustar/regtype", TEMPDIR)
        try:
            cpio.extract("ustar/lnktype", TEMPDIR)
        except EnvironmentError, e:
            if e.errno == errno.ENOENT:
                self.fail("hardlink not extracted properly")

        data = open(os.path.join(TEMPDIR, "ustar/lnktype"), "rb").read()
        self.assertEqual(md5sum(data), md5_regtype)

        try:
            cpio.extract("ustar/symtype", TEMPDIR)
        except EnvironmentError, e:
            if e.errno == errno.ENOENT:
                self.fail("symlink not extracted properly")

        data = open(os.path.join(TEMPDIR, "ustar/symtype"), "rb").read()
        self.assertEqual(md5sum(data), md5_regtype)


class StreamReadTest(ReadTest):

    mode="r|"

    def test_fileobj_regular_file(self):
        cpioinfo = self.cpio.next() # get "regtype" (can't use getmember)
        fobj = self.cpio.extractfile(cpioinfo)
        data = fobj.read()
        self.assert_((len(data), md5sum(data)) == (cpioinfo.size, md5_regtype),
                "regular file extraction failed")

    def test_provoke_stream_error(self):
        cpioinfos = self.cpio.getmembers()
        f = self.cpio.extractfile(cpioinfos[0]) # read the first member
        self.assertRaises(cpiofile.StreamError, f.read)

    def test_compare_members(self):
        cpio1 = cpiofile.open(cpioname, encoding="iso8859-1")
        cpio2 = self.cpio

        while True:
            t1 = cpio1.next()
            t2 = cpio2.next()
            if t1 is None:
                break
            self.assert_(t2 is not None, "stream.next() failed.")

            if t2.islnk() or t2.issym():
                self.assertRaises(cpiofile.StreamError, cpio2.extractfile, t2)
                continue

            v1 = cpio1.extractfile(t1)
            v2 = cpio2.extractfile(t2)
            if v1 is None:
                continue
            self.assert_(v2 is not None, "stream.extractfile() failed")
            self.assert_(v1.read() == v2.read(), "stream extraction failed")

        cpio1.close()


class DetectReadTest(unittest.TestCase):

    def _testfunc_file(self, name, mode):
        try:
            cpiofile.open(name, mode)
        except cpiofile.ReadError:
            self.fail()

    def _testfunc_fileobj(self, name, mode):
        try:
            cpiofile.open(name, mode, fileobj=open(name, "rb"))
        except cpiofile.ReadError:
            self.fail()

    def _test_modes(self, testfunc):
        testfunc(cpioname, "r")
        testfunc(cpioname, "r:")
        testfunc(cpioname, "r:*")
        testfunc(cpioname, "r|")
        testfunc(cpioname, "r|*")

        if gzip:
            self.assertRaises(cpiofile.ReadError, cpiofile.open, cpioname, mode="r:gz")
            self.assertRaises(cpiofile.ReadError, cpiofile.open, cpioname, mode="r|gz")
            self.assertRaises(cpiofile.ReadError, cpiofile.open, gzipname, mode="r:")
            self.assertRaises(cpiofile.ReadError, cpiofile.open, gzipname, mode="r|")

            testfunc(gzipname, "r")
            testfunc(gzipname, "r:*")
            testfunc(gzipname, "r:gz")
            testfunc(gzipname, "r|*")
            testfunc(gzipname, "r|gz")

        if bz2:
            self.assertRaises(cpiofile.ReadError, cpiofile.open, cpioname, mode="r:bz2")
            self.assertRaises(cpiofile.ReadError, cpiofile.open, cpioname, mode="r|bz2")
            self.assertRaises(cpiofile.ReadError, cpiofile.open, bz2name, mode="r:")
            self.assertRaises(cpiofile.ReadError, cpiofile.open, bz2name, mode="r|")

            testfunc(bz2name, "r")
            testfunc(bz2name, "r:*")
            testfunc(bz2name, "r:bz2")
            testfunc(bz2name, "r|*")
            testfunc(bz2name, "r|bz2")

    def test_detect_file(self):
        self._test_modes(self._testfunc_file)

    def test_detect_fileobj(self):
        self._test_modes(self._testfunc_fileobj)


class MemberReadTest(ReadTest):

    def _test_member(self, cpioinfo, chksum=None, **kwargs):
        if chksum is not None:
            self.assert_(md5sum(self.cpio.extractfile(cpioinfo).read()) == chksum,
                    "wrong md5sum for %s" % cpioinfo.name)

        kwargs["mtime"] = 07606136617
        kwargs["uid"] = 1000
        kwargs["gid"] = 100
        if "old-v7" not in cpioinfo.name:
            # V7 tar can't handle alphabetic owners.
            kwargs["uname"] = "cpiofile"
            kwargs["gname"] = "cpiofile"
        for k, v in kwargs.iteritems():
            self.assert_(getattr(cpioinfo, k) == v,
                    "wrong value in %s field of %s" % (k, cpioinfo.name))

    def test_find_regtype(self):
        cpioinfo = self.cpio.getmember("ustar/regtype")
        self._test_member(cpioinfo, size=7011, chksum=md5_regtype)

    def test_find_conttype(self):
        cpioinfo = self.cpio.getmember("ustar/conttype")
        self._test_member(cpioinfo, size=7011, chksum=md5_regtype)

    def test_find_dirtype(self):
        cpioinfo = self.cpio.getmember("ustar/dirtype")
        self._test_member(cpioinfo, size=0)

    def test_find_dirtype_with_size(self):
        cpioinfo = self.cpio.getmember("ustar/dirtype-with-size")
        self._test_member(cpioinfo, size=255)

    def test_find_lnktype(self):
        cpioinfo = self.cpio.getmember("ustar/lnktype")
        self._test_member(cpioinfo, size=0, linkname="ustar/regtype")

    def test_find_symtype(self):
        cpioinfo = self.cpio.getmember("ustar/symtype")
        self._test_member(cpioinfo, size=0, linkname="regtype")

    def test_find_blktype(self):
        cpioinfo = self.cpio.getmember("ustar/blktype")
        self._test_member(cpioinfo, size=0, devmajor=3, devminor=0)

    def test_find_chrtype(self):
        cpioinfo = self.cpio.getmember("ustar/chrtype")
        self._test_member(cpioinfo, size=0, devmajor=1, devminor=3)

    def test_find_fifotype(self):
        cpioinfo = self.cpio.getmember("ustar/fifotype")
        self._test_member(cpioinfo, size=0)

    def test_find_sparse(self):
        cpioinfo = self.cpio.getmember("ustar/sparse")
        self._test_member(cpioinfo, size=86016, chksum=md5_sparse)

    def test_find_umlauts(self):
        cpioinfo = self.cpio.getmember("ustar/umlauts-ÄÖÜäöüß")
        self._test_member(cpioinfo, size=7011, chksum=md5_regtype)

    def test_find_ustar_longname(self):
        name = "ustar/" + "12345/" * 39 + "1234567/longname"
        self.assert_(name in self.tar.getnames())

    def test_find_regtype_oldv7(self):
        tarinfo = self.tar.getmember("misc/regtype-old-v7")
        self._test_member(tarinfo, size=7011, chksum=md5_regtype)

    def test_find_pax_umlauts(self):
        self.tar = tarfile.open(self.tarname, mode=self.mode, encoding="iso8859-1")
        tarinfo = self.tar.getmember("pax/umlauts-ÄÖÜäöüß")
        self._test_member(tarinfo, size=7011, chksum=md5_regtype)


class LongnameTest(ReadTest):

    def test_read_longname(self):
        # Test reading of longname (bug #1471427).
        longname = self.subdir + "/" + "123/" * 125 + "longname"
        try:
            cpioinfo = self.cpio.getmember(longname)
        except KeyError:
            self.fail("longname not found")
        self.assert_(cpioinfo.type != cpiofile.DIRTYPE, "read longname as dirtype")

    def test_read_longlink(self):
        longname = self.subdir + "/" + "123/" * 125 + "longname"
        longlink = self.subdir + "/" + "123/" * 125 + "longlink"
        try:
            cpioinfo = self.cpio.getmember(longlink)
        except KeyError:
            self.fail("longlink not found")
        self.assert_(cpioinfo.linkname == longname, "linkname wrong")

    def test_truncated_longname(self):
        longname = self.subdir + "/" + "123/" * 125 + "longname"
        cpioinfo = self.cpio.getmember(longname)
        offset = cpioinfo.offset
        self.cpio.fileobj.seek(offset)
        fobj = StringIO.StringIO(self.cpio.fileobj.read(3 * 512))
        self.assertRaises(cpiofile.ReadError, cpiofile.open, name="foo.cpio", fileobj=fobj)

    def test_header_offset(self):
        # Test if the start offset of the TarInfo object includes
        # the preceding extended header.
        longname = self.subdir + "/" + "123/" * 125 + "longname"
        offset = self.tar.getmember(longname).offset
        fobj = open(tarname)
        fobj.seek(offset)
        tarinfo = tarfile.TarInfo.frombuf(fobj.read(512))
        self.assertEqual(tarinfo.type, self.longnametype)


class GNUReadTest(LongnameTest):

    subdir = "gnu"
    longnametype = tarfile.GNUTYPE_LONGNAME

    def test_sparse_file(self):
        cpioinfo1 = self.cpio.getmember("ustar/sparse")
        fobj1 = self.cpio.extractfile(cpioinfo1)
        cpioinfo2 = self.cpio.getmember("gnu/sparse")
        fobj2 = self.cpio.extractfile(cpioinfo2)
        self.assert_(fobj1.read() == fobj2.read(),
                "sparse file extraction failed")


class PaxReadTest(LongnameTest):

    subdir = "pax"
    longnametype = tarfile.XHDTYPE

    def test_pax_global_headers(self):
        tar = tarfile.open(tarname, encoding="iso8859-1")

        tarinfo = tar.getmember("pax/regtype1")
        self.assertEqual(tarinfo.uname, "foo")
        self.assertEqual(tarinfo.gname, "bar")
        self.assertEqual(tarinfo.pax_headers.get("VENDOR.umlauts"), u"ÄÖÜäöüß")

        tarinfo = tar.getmember("pax/regtype2")
        self.assertEqual(tarinfo.uname, "")
        self.assertEqual(tarinfo.gname, "bar")
        self.assertEqual(tarinfo.pax_headers.get("VENDOR.umlauts"), u"ÄÖÜäöüß")

        tarinfo = tar.getmember("pax/regtype3")
        self.assertEqual(tarinfo.uname, "tarfile")
        self.assertEqual(tarinfo.gname, "tarfile")
        self.assertEqual(tarinfo.pax_headers.get("VENDOR.umlauts"), u"ÄÖÜäöüß")

    def test_pax_number_fields(self):
        # All following number fields are read from the pax header.
        tar = tarfile.open(tarname, encoding="iso8859-1")
        tarinfo = tar.getmember("pax/regtype4")
        self.assertEqual(tarinfo.size, 7011)
        self.assertEqual(tarinfo.uid, 123)
        self.assertEqual(tarinfo.gid, 123)
        self.assertEqual(tarinfo.mtime, 1041808783.0)
        self.assertEqual(type(tarinfo.mtime), float)
        self.assertEqual(float(tarinfo.pax_headers["atime"]), 1041808783.0)
        self.assertEqual(float(tarinfo.pax_headers["ctime"]), 1041808783.0)


class WriteTest(unittest.TestCase):

    mode = "w:"

    def test_100_char_name(self):
        # The name field in a tar header stores strings of at most 100 chars.
        # If a string is shorter than 100 chars it has to be padded with '\0',
        # which implies that a string of exactly 100 chars is stored without
        # a trailing '\0'.
        name = "0123456789" * 10
        tar = tarfile.open(tmpname, self.mode)
        t = tarfile.TarInfo(name)
        tar.addfile(t)
        tar.close()

        tar = tarfile.open(tmpname)
        self.assert_(tar.getnames()[0] == name,
                "failed to store 100 char filename")
        tar.close()

    def test_cpio_size(self):
        # Test for bug #1013882.
        cpio = cpiofile.open(tmpname, self.mode)
        path = os.path.join(TEMPDIR, "file")
        fobj = open(path, "wb")
        fobj.write("aaa")
        fobj.close()
        cpio.add(path)
        cpio.close()
        self.assert_(os.path.getsize(tmpname) > 0,
                "cpiofile is empty")

    # The test_*_size tests test for bug #1167128.
    def test_file_size(self):
        cpio = cpiofile.open(tmpname, self.mode)

        path = os.path.join(TEMPDIR, "file")
        fobj = open(path, "wb")
        fobj.close()
        cpioinfo = cpio.getcpioinfo(path)
        self.assertEqual(cpioinfo.size, 0)

        fobj = open(path, "wb")
        fobj.write("aaa")
        fobj.close()
        cpioinfo = cpio.getcpioinfo(path)
        self.assertEqual(cpioinfo.size, 3)

        cpio.close()

    def test_directory_size(self):
        path = os.path.join(TEMPDIR, "directory")
        os.mkdir(path)
        try:
            cpio = cpiofile.open(tmpname, self.mode)
            cpioinfo = cpio.getcpioinfo(path)
            self.assertEqual(cpioinfo.size, 0)
        finally:
            os.rmdir(path)

    def test_link_size(self):
        if hasattr(os, "link"):
            link = os.path.join(TEMPDIR, "link")
            target = os.path.join(TEMPDIR, "link_target")
            open(target, "wb").close()
            os.link(target, link)
            try:
                cpio = cpiofile.open(tmpname, self.mode)
                cpioinfo = cpio.getcpioinfo(link)
                self.assertEqual(cpioinfo.size, 0)
            finally:
                os.remove(target)
                os.remove(link)

    def test_symlink_size(self):
        if hasattr(os, "symlink"):
            path = os.path.join(TEMPDIR, "symlink")
            os.symlink("link_target", path)
            try:
                cpio = cpiofile.open(tmpname, self.mode)
                cpioinfo = cpio.getcpioinfo(path)
                self.assertEqual(cpioinfo.size, 0)
            finally:
                os.remove(path)

    def test_add_self(self):
        # Test for #1257255.
        dstname = os.path.abspath(tmpname)

        cpio = cpiofile.open(tmpname, self.mode)
        self.assert_(cpio.name == dstname, "archive name must be absolute")

        cpio.add(dstname)
        self.assert_(cpio.getnames() == [], "added the archive to itself")

        cwd = os.getcwd()
        os.chdir(TEMPDIR)
        cpio.add(dstname)
        os.chdir(cwd)
        self.assert_(cpio.getnames() == [], "added the archive to itself")


class StreamWriteTest(unittest.TestCase):

    mode = "w|"

    def test_stream_padding(self):
        # Test for bug #1543303.
        cpio = cpiofile.open(tmpname, self.mode)
        cpio.close()

        if self.mode.endswith("gz"):
            fobj = gzip.GzipFile(tmpname)
            data = fobj.read()
            fobj.close()
        elif self.mode.endswith("bz2"):
            dec = bz2.BZ2Decompressor()
            data = open(tmpname, "rb").read()
            data = dec.decompress(data)
            self.assert_(len(dec.unused_data) == 0,
                    "found trailing data")
        else:
            fobj = open(tmpname, "rb")
            data = fobj.read()
            fobj.close()

        self.assert_(data.count("\0") == cpiofile.RECORDSIZE,
                         "incorrect zero padding")


class GNUWriteTest(unittest.TestCase):
    # This testcase checks for correct creation of GNU Longname
    # and Longlink extended headers (cp. bug #812325).

    def _length(self, s):
        blocks, remainder = divmod(len(s) + 1, 512)
        if remainder:
            blocks += 1
        return blocks * 512

    def _calc_size(self, name, link=None):
        # Initial cpio header
        count = 512

        if len(name) > cpiofile.LENGTH_NAME:
            # GNU longname extended header + longname
            count += 512
            count += self._length(name)
        if link is not None and len(link) > cpiofile.LENGTH_LINK:
            # GNU longlink extended header + longlink
            count += 512
            count += self._length(link)
        return count

    def _test(self, name, link=None):
        cpioinfo = cpiofile.CpioInfo(name)
        if link:
            cpioinfo.linkname = link
            cpioinfo.type = cpiofile.LNKTYPE

        cpio = cpiofile.open(tmpname, "w")
        cpio.format = cpiofile.GNU_FORMAT
        cpio.addfile(cpioinfo)

        v1 = self._calc_size(name, link)
        v2 = cpio.offset
        self.assert_(v1 == v2, "GNU longname/longlink creation failed")

        cpio.close()

        cpio = cpiofile.open(tmpname)
        member = cpio.next()
        self.failIf(member is None, "unable to read longname member")
        self.assert_(cpioinfo.name == member.name and \
                     cpioinfo.linkname == member.linkname, \
                     "unable to read longname member")

    def test_longname_1023(self):
        self._test(("longnam/" * 127) + "longnam")

    def test_longname_1024(self):
        self._test(("longnam/" * 127) + "longname")

    def test_longname_1025(self):
        self._test(("longnam/" * 127) + "longname_")

    def test_longlink_1023(self):
        self._test("name", ("longlnk/" * 127) + "longlnk")

    def test_longlink_1024(self):
        self._test("name", ("longlnk/" * 127) + "longlink")

    def test_longlink_1025(self):
        self._test("name", ("longlnk/" * 127) + "longlink_")

    def test_longnamelink_1023(self):
        self._test(("longnam/" * 127) + "longnam",
                   ("longlnk/" * 127) + "longlnk")

    def test_longnamelink_1024(self):
        self._test(("longnam/" * 127) + "longname",
                   ("longlnk/" * 127) + "longlink")

    def test_longnamelink_1025(self):
        self._test(("longnam/" * 127) + "longname_",
                   ("longlnk/" * 127) + "longlink_")


class HardlinkTest(unittest.TestCase):
    # Test the creation of LNKTYPE (hardlink) members in an archive.

    def setUp(self):
        self.foo = os.path.join(TEMPDIR, "foo")
        self.bar = os.path.join(TEMPDIR, "bar")

        fobj = open(self.foo, "wb")
        fobj.write("foo")
        fobj.close()

        os.link(self.foo, self.bar)

        self.cpio = cpiofile.open(tmpname, "w")
        self.cpio.add(self.foo)

    def tearDown(self):
        os.remove(self.foo)
        os.remove(self.bar)

    def test_add_twice(self):
        # The same name will be added as a REGTYPE every
        # time regardless of st_nlink.
        cpioinfo = self.cpio.getcpioinfo(self.foo)
        self.assert_(cpioinfo.type == cpiofile.REGTYPE,
                "add file as regular failed")

    def test_add_hardlink(self):
        cpioinfo = self.cpio.getcpioinfo(self.bar)
        self.assert_(cpioinfo.type == cpiofile.LNKTYPE,
                "add file as hardlink failed")

    def test_dereference_hardlink(self):
        self.cpio.dereference = True
        cpioinfo = self.cpio.getcpioinfo(self.bar)
        self.assert_(cpioinfo.type == cpiofile.REGTYPE,
                "dereferencing hardlink failed")


class PaxWriteTest(GNUWriteTest):

    def _test(self, name, link=None):
        # See GNUWriteTest.
        cpioinfo = cpiofile.CpioInfo(name)
        if link:
            cpioinfo.linkname = link
            cpioinfo.type = cpiofile.LNKTYPE

        cpio = cpiofile.open(tmpname, "w", format=cpiofile.PAX_FORMAT)
        cpio.addfile(cpioinfo)
        cpio.close()

        tar = tarfile.open(tmpname)
        if link:
            l = tar.getmembers()[0].linkname
            self.assert_(link == l, "PAX longlink creation failed")
        else:
            n = tar.getmembers()[0].name
            self.assert_(name == n, "PAX longname creation failed")

    def test_pax_global_header(self):
        pax_headers = {
                u"foo": u"bar",
                u"uid": u"0",
                u"mtime": u"1.23",
                u"test": u"äöü",
                u"äöü": u"test"}

        tar = tarfile.open(tmpname, "w", format=tarfile.PAX_FORMAT, \
                pax_headers=pax_headers)
        tar.addfile(tarfile.TarInfo("test"))
        tar.close()

        # Test if the global header was written correctly.
        tar = tarfile.open(tmpname, encoding="iso8859-1")
        self.assertEqual(tar.pax_headers, pax_headers)
        self.assertEqual(tar.getmembers()[0].pax_headers, pax_headers)

        # Test if all the fields are unicode.
        for key, val in tar.pax_headers.iteritems():
            self.assert_(type(key) is unicode)
            self.assert_(type(val) is unicode)
            if key in tarfile.PAX_NUMBER_FIELDS:
                try:
                    tarfile.PAX_NUMBER_FIELDS[key](val)
                except (TypeError, ValueError):
                    self.fail("unable to convert pax header field")

    def test_pax_extended_header(self):
        # The fields from the pax header have priority over the
        # TarInfo.
        pax_headers = {u"path": u"foo", u"uid": u"123"}

        tar = tarfile.open(tmpname, "w", format=tarfile.PAX_FORMAT, encoding="iso8859-1")
        t = tarfile.TarInfo()
        t.name = u"äöü"     # non-ASCII
        t.uid = 8**8        # too large
        t.pax_headers = pax_headers
        tar.addfile(t)
        tar.close()

        tar = tarfile.open(tmpname, encoding="iso8859-1")
        t = tar.getmembers()[0]
        self.assertEqual(t.pax_headers, pax_headers)
        self.assertEqual(t.name, "foo")
        self.assertEqual(t.uid, 123)


class UstarUnicodeTest(unittest.TestCase):
    # All *UnicodeTests FIXME

    format = tarfile.USTAR_FORMAT

    def test_iso8859_1_filename(self):
        self._test_unicode_filename("iso8859-1")

    def test_utf7_filename(self):
        self._test_unicode_filename("utf7")

    def test_utf8_filename(self):
        self._test_unicode_filename("utf8")

    def _test_unicode_filename(self, encoding):
        tar = tarfile.open(tmpname, "w", format=self.format, encoding=encoding, errors="strict")
        name = u"äöü"
        tar.addfile(tarfile.TarInfo(name))
        tar.close()

        tar = tarfile.open(tmpname, encoding=encoding)
        self.assert_(type(tar.getnames()[0]) is not unicode)
        self.assertEqual(tar.getmembers()[0].name, name.encode(encoding))
        tar.close()

    def test_unicode_filename_error(self):
        tar = tarfile.open(tmpname, "w", format=self.format, encoding="ascii", errors="strict")
        tarinfo = tarfile.TarInfo()

        tarinfo.name = "äöü"
        if self.format == tarfile.PAX_FORMAT:
            self.assertRaises(UnicodeError, tar.addfile, tarinfo)
        else:
            tar.addfile(tarinfo)

        tarinfo.name = u"äöü"
        self.assertRaises(UnicodeError, tar.addfile, tarinfo)

        tarinfo.name = "foo"
        tarinfo.uname = u"äöü"
        self.assertRaises(UnicodeError, tar.addfile, tarinfo)

    def test_unicode_argument(self):
        tar = tarfile.open(tarname, "r", encoding="iso8859-1", errors="strict")
        for t in tar:
            self.assert_(type(t.name) is str)
            self.assert_(type(t.linkname) is str)
            self.assert_(type(t.uname) is str)
            self.assert_(type(t.gname) is str)
        tar.close()

    def test_uname_unicode(self):
        for name in (u"äöü", "äöü"):
            t = tarfile.TarInfo("foo")
            t.uname = name
            t.gname = name

            fobj = StringIO.StringIO()
            tar = tarfile.open("foo.tar", mode="w", fileobj=fobj, format=self.format, encoding="iso8859-1")
            tar.addfile(t)
            tar.close()
            fobj.seek(0)

            tar = tarfile.open("foo.tar", fileobj=fobj, encoding="iso8859-1")
            t = tar.getmember("foo")
            self.assertEqual(t.uname, "äöü")
            self.assertEqual(t.gname, "äöü")


class GNUUnicodeTest(UstarUnicodeTest):

    format = tarfile.GNU_FORMAT


class PaxUnicodeTest(UstarUnicodeTest):

    format = tarfile.PAX_FORMAT

    def _create_unicode_name(self, name):
        tar = tarfile.open(tmpname, "w", format=self.format)
        t = tarfile.TarInfo()
        t.pax_headers["path"] = name
        tar.addfile(t)
        tar.close()

    def test_error_handlers(self):
        # Test if the unicode error handlers work correctly for characters
        # that cannot be expressed in a given encoding.
        self._create_unicode_name(u"äöü")

        for handler, name in (("utf-8", u"äöü".encode("utf8")),
                    ("replace", "???"), ("ignore", "")):
            tar = tarfile.open(tmpname, format=self.format, encoding="ascii",
                    errors=handler)
            self.assertEqual(tar.getnames()[0], name)

        self.assertRaises(UnicodeError, tarfile.open, tmpname,
                encoding="ascii", errors="strict")

    def test_error_handler_utf8(self):
        # Create a pathname that has one component representable using
        # iso8859-1 and the other only in iso8859-15.
        self._create_unicode_name(u"äöü/€")

        tar = tarfile.open(tmpname, format=self.format, encoding="iso8859-1",
                errors="utf-8")
        self.assertEqual(tar.getnames()[0], "äöü/" + u"€".encode("utf8"))


class AppendTest(unittest.TestCase):
    # Test append mode (cp. patch #1652681).

    def setUp(self):
        self.cpioname = tmpname
        if os.path.exists(self.cpioname):
            os.remove(self.cpioname)

    def _add_testfile(self, fileobj=None):
        cpio = cpiofile.open(self.cpioname, "a", fileobj=fileobj)
        cpio.addfile(cpiofile.CpioInfo("bar"))
        cpio.close()

    def _create_testcpio(self, mode="w:"):
        src = cpiofile.open(cpioname, encoding="iso8859-1")
        t = src.getmember("ustar/regtype")
        t.name = "foo"
        f = src.extractfile(t)
        cpio = cpiofile.open(self.cpioname, mode)
        cpio.addfile(t, f)
        cpio.close()

    def _test(self, names=["bar"], fileobj=None):
        cpio = cpiofile.open(self.cpioname, fileobj=fileobj)
        self.assertEqual(cpio.getnames(), names)

    def test_non_existing(self):
        self._add_testfile()
        self._test()

    def test_empty(self):
        open(self.cpioname, "w").close()
        self._add_testfile()
        self._test()

    def test_empty_fileobj(self):
        fobj = StringIO.StringIO()
        self._add_testfile(fobj)
        fobj.seek(0)
        self._test(fileobj=fobj)

    def test_fileobj(self):
        self._create_testcpio()
        data = open(self.cpioname).read()
        fobj = StringIO.StringIO(data)
        self._add_testfile(fobj)
        fobj.seek(0)
        self._test(names=["foo", "bar"], fileobj=fobj)

    def test_existing(self):
        self._create_testcpio()
        self._add_testfile()
        self._test(names=["foo", "bar"])

    def test_append_gz(self):
        if gzip is None:
            return
        self._create_testcpio("w:gz")
        self.assertRaises(cpiofile.ReadError, cpiofile.open, tmpname, "a")

    def test_append_bz2(self):
        if bz2 is None:
            return
        self._create_testcpio("w:bz2")
        self.assertRaises(cpiofile.ReadError, cpiofile.open, tmpname, "a")


class LimitsTest(unittest.TestCase):

    def test_ustar_limits(self):
        # 100 char name
        tarinfo = tarfile.TarInfo("0123456789" * 10)
        tarinfo.tobuf(tarfile.USTAR_FORMAT)

        # 101 char name that cannot be stored
        tarinfo = tarfile.TarInfo("0123456789" * 10 + "0")
        self.assertRaises(ValueError, tarinfo.tobuf, tarfile.USTAR_FORMAT)

        # 256 char name with a slash at pos 156
        tarinfo = tarfile.TarInfo("123/" * 62 + "longname")
        tarinfo.tobuf(tarfile.USTAR_FORMAT)

        # 256 char name that cannot be stored
        tarinfo = tarfile.TarInfo("1234567/" * 31 + "longname")
        self.assertRaises(ValueError, tarinfo.tobuf, tarfile.USTAR_FORMAT)

        # 512 char name
        tarinfo = tarfile.TarInfo("123/" * 126 + "longname")
        self.assertRaises(ValueError, tarinfo.tobuf, tarfile.USTAR_FORMAT)

        # 512 char linkname
        tarinfo = tarfile.TarInfo("longlink")
        tarinfo.linkname = "123/" * 126 + "longname"
        self.assertRaises(ValueError, tarinfo.tobuf, tarfile.USTAR_FORMAT)

        # uid > 8 digits
        tarinfo = tarfile.TarInfo("name")
        tarinfo.uid = 010000000
        self.assertRaises(ValueError, tarinfo.tobuf, tarfile.USTAR_FORMAT)

    def test_gnu_limits(self):
        tarinfo = tarfile.TarInfo("123/" * 126 + "longname")
        tarinfo.tobuf(tarfile.GNU_FORMAT)

        tarinfo = tarfile.TarInfo("longlink")
        tarinfo.linkname = "123/" * 126 + "longname"
        tarinfo.tobuf(tarfile.GNU_FORMAT)

        # uid >= 256 ** 7
        tarinfo = tarfile.TarInfo("name")
        tarinfo.uid = 04000000000000000000L
        self.assertRaises(ValueError, tarinfo.tobuf, tarfile.GNU_FORMAT)

    def test_pax_limits(self):
        tarinfo = tarfile.TarInfo("123/" * 126 + "longname")
        tarinfo.tobuf(tarfile.PAX_FORMAT)

        tarinfo = tarfile.TarInfo("longlink")
        tarinfo.linkname = "123/" * 126 + "longname"
        tarinfo.tobuf(tarfile.PAX_FORMAT)

        tarinfo = tarfile.TarInfo("name")
        tarinfo.uid = 04000000000000000000L
        tarinfo.tobuf(tarfile.PAX_FORMAT)


class GzipMiscReadTest(MiscReadTest):
    cpioname = gzipname
    mode = "r:gz"
class GzipUstarReadTest(UstarReadTest):
    tarname = gzipname
    mode = "r:gz"
class GzipStreamReadTest(StreamReadTest):
    cpioname = gzipname
    mode = "r|gz"
class GzipWriteTest(WriteTest):
    mode = "w:gz"
class GzipStreamWriteTest(StreamWriteTest):
    mode = "w|gz"


class Bz2MiscReadTest(MiscReadTest):
    cpioname = bz2name
    mode = "r:bz2"
class Bz2UstarReadTest(UstarReadTest):
    tarname = bz2name
    mode = "r:bz2"
class Bz2StreamReadTest(StreamReadTest):
    cpioname = bz2name
    mode = "r|bz2"
class Bz2WriteTest(WriteTest):
    mode = "w:bz2"
class Bz2StreamWriteTest(StreamWriteTest):
    mode = "w|bz2"

def test_main():
    if not os.path.exists(TEMPDIR):
        os.mkdir(TEMPDIR)

    tests = [
        UstarReadTest,
        MiscReadTest,
        StreamReadTest,
        DetectReadTest,
        MemberReadTest,
        GNUReadTest,
        PaxReadTest,
        WriteTest,
        StreamWriteTest,
        GNUWriteTest,
        PaxWriteTest,
        UstarUnicodeTest,
        GNUUnicodeTest,
        PaxUnicodeTest,
        AppendTest,
        LimitsTest,
    ]

    if hasattr(os, "link"):
        tests.append(HardlinkTest)

    fobj = open(cpioname, "rb")
    data = fobj.read()
    fobj.close()

    if gzip:
        # Create testcpio.cpio.gz and add gzip-specific tests.
        cpio = gzip.open(gzipname, "wb")
        cpio.write(data)
        cpio.close()

        tests += [
            GzipMiscReadTest,
            GzipUstarReadTest,
            GzipStreamReadTest,
            GzipWriteTest,
            GzipStreamWriteTest,
        ]

    if bz2:
        # Create testcpio.cpio.bz2 and add bz2-specific tests.
        cpio = bz2.BZ2File(bz2name, "wb")
        cpio.write(data)
        cpio.close()

        tests += [
            Bz2MiscReadTest,
            Bz2UstarReadTest,
            Bz2StreamReadTest,
            Bz2WriteTest,
            Bz2StreamWriteTest,
        ]

    try:
        test_support.run_unittest(*tests)
    finally:
        if os.path.exists(TEMPDIR):
            shutil.rmtree(TEMPDIR)

if __name__ == "__main__":
    test_main()
