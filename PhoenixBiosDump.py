#!/usr/bin/env python3
# Phoenix BIOS Dump
# 2021-09-29 version 0.1
# Copyright (c) 2021 @marbocub
# Released under the MIT license
# https://opensource.org/licenses/mit-license.php

import sys, os, io, struct, ctypes, copy

class MicrocodeImage():
    class IntelMicrocodeHeader(ctypes.LittleEndianStructure):
        _fields_ = (
            ("HeaderVerion",    ctypes.c_uint32),
            ("UpdateRevision",  ctypes.c_uint32),
            ("Date",            ctypes.c_uint32),
            ("Signature",       ctypes.c_uint32),
            ("Checksum",        ctypes.c_uint32),
            ("LoaderRevision",  ctypes.c_uint32),
            ("ProcessorFlags",  ctypes.c_uint32),
            ("DataSize",        ctypes.c_uint32),
            ("TotalSize",       ctypes.c_uint32),
        )

        def __init__(self):
            super().__init__()
            self.microcode = None

    def __init__(self):
        self._image = None
        self._updates = []

    def add(self, stringimage):
        self._updates += [stringimage]

    @property
    def hasUpdates(self):
        if len(self._updates) > 0:
            return True
        else:
            return False

    @property
    def list(self):
        entries = []
        pos = 0
        while True:
            pos = self._image.find(b'\x01\x00\x00\x00', pos)
            if pos < 0:
                break
            entry = self._analyze(self._image[pos:])
            entries += [entry]
            pos += entry.TotalSize
        return entries

    @property
    def updatelist(self):
        entries = []
        for update in self._updates:
            entry = self._analyze(update)
            entries += [entry]
        return entries

    @property
    def image(self):
        if self._image == None:
            return self._image
        if len(self._updates) == 0:
            return self._image

        (entries, forward, reverse) = self._merge()

        size = len(self._image)
        with io.BytesIO() as stream:
            base = (ctypes.c_ubyte * size)()
            ctypes.memset(base, 0xff, size)
            stream.write(base)
            stream.seek(0)

            pos_head = 0
            pos_tail = size
            i = 0
            for entry in forward + list(reversed(reverse)):
                size = (-((-entry.TotalSize) // 0x800)) * 0x800

                microcode = (ctypes.c_ubyte * size)()
                ctypes.memset(microcode, 0, size)
                ctypes.memmove(microcode, entry.microcode, entry.TotalSize)

                if i < len(forward):
                    stream.seek(pos_head)
                    stream.write(microcode)
                    pos_head += size
                else:
                    pos_tail -= size
                    stream.seek(pos_tail)
                    stream.write(microcode)
                i += 1

            stream.seek(0)
            image = stream.read()
        
        return image

    @image.setter
    def image(self, image):
        self._image = image

    def _analyze(self, microcode):
        m = self.IntelMicrocodeHeader.from_buffer_copy(microcode)
        m.__init__()
        m.microcode = microcode[:m.TotalSize]
        return m

    def _merge(self):
        threshold = self._image.find(b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF')
        if threshold < 0:
            threshold = len(self._image)

        pos = 0
        forward = 0
        entrydict = {}
        while True:
            pos = self._image.find(b'\x01\x00\x00\x00', pos)
            if pos < 0:
                break
            if pos < threshold:
                forward += 1
            entry = self._analyze(self._image[pos:])
            entrydict[entry.Signature] = entry
            pos += entry.TotalSize

        for update in self._updates:
            entry = self._analyze(update)
            entrydict[entry.Signature] = entry

        entries = list(entrydict.values())

        return (entries, entries[:forward], entries[forward:])

class PhoenixBios():
    class VolumeDirHeader(ctypes.LittleEndianStructure):
        _fields_ = (
            ('flag1',       ctypes.c_uint16),
            ('headersize',  ctypes.c_uint16),
            ('bodysize',    ctypes.c_uint32),
        )

    class VolumeDirEntry(ctypes.LittleEndianStructure):
        _fields_ = (
            ('_uuid',       ctypes.c_ubyte * 16),
            ('address',     ctypes.c_uint32),
            ('size',        ctypes.c_uint32),
        )

        def __init__(self):
            super().__init__()
            self.body = None
            self.modules = None

        def save(self, overwrite = False):
            name = self.name
            if not overwrite and os.path.exists(name):
                count = 1
                while True:
                    altname = name + str(count)
                    if os.path.exists(altname):
                        count = count + 1
                        continue
                    break
                name = altname

            if len(name) > 0:
                with open(name, 'wb') as modulefile:
                    modulefile.write(self.body)

        @property
        def name(self):
            uuiddict = {
                bytes.fromhex("630FAEF68C5F1643A2EA76B9AF762756") : "HOLE",
                bytes.fromhex("BA1FD9FE7BD3EA4E87292EF29FB37A78") : "MODULE",
                bytes.fromhex("FDE821FD2525954ABB9047EC5763FF9E") : "ESCD",
                bytes.fromhex("D01023C054D73945B0CF9F9F2618D4A9") : "SETUP",
                bytes.fromhex("112BF272ABCEE242958A0DA1622D94E3") : "UEFIV",
                bytes.fromhex("12ED2C42E5AEB94384E0AFB3E416254D") : "DMIV",
            }
            return uuiddict[self.uuid]

        @property
        def uuid(self):
            return bytes(self._uuid)

    class ModuleHeader(ctypes.LittleEndianStructure):
        _fields_ = (
            ('flag1',       ctypes.c_ubyte),
            ('flag2',       ctypes.c_ubyte),
            ('headersum',   ctypes.c_ubyte),
            ('checksum',    ctypes.c_ubyte),
            ('_size',       ctypes.c_ubyte * 3),
            ('_type',       ctypes.c_ubyte),
            ('_name',       ctypes.c_ubyte * 16),
        )

        def __init__(self):
            super().__init__()
            self.offset = None
            self.body = None
            self.number = None

        def save(self, overwrite = False):
            name = self.name
            if not overwrite and os.path.exists(name):
                count = 1
                while True:
                    altname = name + str(count)
                    if os.path.exists(altname):
                        count = count + 1
                        continue
                    break
                name = altname

            if len(name) > 0:
                with open(name, 'wb') as modulefile:
                    modulefile.write(self.body)

        @property
        def size(self):
            return (self._size[2] << 16) | (self._size[1] << 8) | self._size[0]

        @property
        def headersize(self):
            return ctypes.sizeof(self)

        @property
        def bodysize(self):
            return self.size - self.headersize

        @property
        def name(self):
            namedict = {
                "_A" : "ACPI",
                "_B" : "BIOSCODE",
                "_C" : "UPDATE",
                "_D" : "DISPLAY",
                "_E" : "SETUP",
                "_G" : 'DECOMPC',
                "_I" : 'BOOTBLOCK',
                "_L" : 'LOGO',
                "_M" : 'MISER',
                "_R" : 'OPROM',
                "_S" : 'STRINGS',
                "_T" : 'TEMPLATE',
                "_U" : 'USER',
                "_W" : 'WAV',
                "_X" : 'ROMEXEC',
                "_*" : 'AUTOGEN',
                "_$" : 'BIOSENTRY',
            }
            if self._type == 0xF0:
                return "GAP"
            name = "".join(map(chr, self._name[:8])).rstrip('\0') + "".join(map(chr, self._name[9:])).rstrip('\0')
            if name[:2] in namedict.keys():
                name = namedict[name[:2]] + name[3:]
            if self.number != None:
                name += str(self.number)
            return name

        @property
        def type(self):
            typedict = {
                0x01 : "BINARY",
                0x02 : "COMPRESS",
            }
            typename = ""
            if self._type in typedict.keys():
                typename += typedict[self._type]
            return typename

    def __init__(self, bios = None):
        self.volumeDirPosition = -1
        self.volumeDir = None
        self.volumeDirEntries = []
        self.bios = bios

    def replace(self, module_name, body):
        address = None
        module = None
        for entry in self.volumeDirEntries:
            for mod in entry.modules:
                if mod.name != module_name:
                    continue
                address = entry.address - self.map_address + mod.offset
                module = mod
                break
            else:
                continue
            break
        if module == None:
            return False
        if len(module.body) != len(body):
            return False

        header = self.ModuleHeader.from_buffer_copy(module)
        header.checksum = self._checksub(body)

        with io.BytesIO() as bios:
            bios.write(self.bios)
            bios.seek(address)
            bios.write(header)
            bios.write(body)
            bios.seek(0)
            self.bios = bios.read()

        return True

    def saveAs(self, filename):
        with open(filename, "wb") as output:
            output.write(self.bios)

    def saveModules(self, overwrite = False):
        for entry in self.volumeDirEntries:
            if len(entry.modules) == 0:
                entry.save(overwrite)
            else:
                for module in entry.modules:
                    module.save(overwrite)

    @property
    def bios(self):
        return self._bios

    @bios.setter
    def bios(self, bios):
        self.volumeDirPosition = -1
        self.volumeDir = None
        self.volumeDirEntries = []
        self._bios = bios

        if bios == None:
            return
        self.volumeDirPosition = self._findVolumeDir()
        if self.volumeDirPosition < 0:
            return

        self.volumeDir = self._readModule(self._bios, self.volumeDirPosition)
        self.volumeDirEntries = self._readVolumeDirEntries(self._bios, self.volumeDir.body)

    def _findVolumeDir(self):
        offset = self._bios.find(b"volumedi\xFFr.bin2")
        if offset > 8:
            offset -= 8
        return offset

    def _readVolumeDirEntries(self, bios, volumedir):
        entries = []
        header = self.VolumeDirHeader.from_buffer_copy(volumedir)
        header.__init__()
        for i in range(header.bodysize//24):
            entry = self.VolumeDirEntry.from_buffer_copy(volumedir, header.headersize + i*ctypes.sizeof(self.VolumeDirEntry))
            entry.__init__()
            pos = entry.address - self.map_address
            if pos < 0:
                entry.body = b''
            else:
                entry.body = bios[pos:pos+entry.size]
            if entry.name == "MODULE":
                entry.modules = self._readModuleEntries(entry.body, 0)
            else:
                entry.modules = []
            entries += [entry]
        return entries

    def _readModule(self, buffer, offset = 0):
        module = self.ModuleHeader.from_buffer_copy(buffer, offset)
        module.__init__()
        module.offset = offset
        module.body = buffer[offset+module.headersize:offset+module.size]
        return module

    def _readModuleEntries(self, buffer, offset = 0):
        entries = []
        while True:
            if offset >= len(buffer):
                break
            if buffer[offset] != 0xF8:
                offset = ((offset // 4) + 1) * 4
                continue
            entry = self._readModule(buffer, offset)
            entries += [entry]
            offset += entry.size
        return entries

    def _checksub(self, buffer):
        sub = 0
        for i in range(len(buffer)):
            sub -= buffer[i]
        return sub & 0xFF

    @property
    def map_address(self):
        if len(self._bios) >= 8388608:
            return 0xff800000
        elif len(self._bios) >= 4194304:
            return 0xffc00000
        elif len(self._bios) >= 2097152:
            return 0xffe00000
        elif len(self._bios) >= 1048576:
            return 0xfff00000
        else:
            return 0

def usage():
    print('usage: PhoenixBiosDump.py biosfile [microcodefile...] [-d]')
    print('')
    print('options:')
    print('  microcodefile\tadd/replace microcode')
    print('  -d           \tdump bios modules')

def main():
    args = sys.argv
    if len(args) < 2:
        usage()
        sys.exit()

    if not os.path.isfile(args[1]):
        print(args[1] + ': file not found')
        sys.exit()

    microcodeimage = MicrocodeImage()
    doDump = False
    for a in args[2:]:
        if a == "-d":
            doDump = True
        elif a[:1] == "-":
            print(a + ": unknown option")
            sys.exit()
        else:
            if not os.path.isfile(a):
                print(a + ": file not found")
                sys.exit()
            with open(a, 'rb') as microcode:
                microcodeimage.add(microcode.read())

    bios = PhoenixBios()
    with open(args[1], 'rb') as biosfile:
        bios.bios = biosfile.read()

    if bios.volumeDirPosition < 0:
        print('volumedir.bin2 not found')
        sys.exit()

    print('PhoenixBiosDump')
    print('')
    print('volumedir.bin2 found at ' + '{:08x}'.format(bios.volumeDirPosition+24))
    print('--------------------------------')
    for entry in bios.volumeDirEntries:
        print('{:08x}'.format(entry.address) + " (" + '{:08x}'.format(entry.size) + ") " + entry.name)
        for module in entry.modules:
            print("         +" + '{:08x}'.format(module.offset) + " :  " + module.name + "\t" + module.type)
            if module.name == "UPDATE0" and module.type == "BINARY":
                microcodeimage.image = module.body
    print('--------------------------------')

    if microcodeimage.image != None:
        print("microcode")
        for code in microcodeimage.list:
            cpuid = '{:x}'.format(code.Signature)
            rev   = '{:02x}'.format(code.UpdateRevision)
            date  = '{:04x}'.format(code.Date & 0xffff) + '/' + '{:02x}'.format(code.Date >> 24 & 0xff) + '/' + '{:02x}'.format(code.Date >> 16 & 0xff)
            print("  " + cpuid + "\t: rev=" + rev + "\tdate=" + date)

        if microcodeimage.hasUpdates:
            print("updates")
            for code in microcodeimage.updatelist:
                cpuid = '{:x}'.format(code.Signature)
                rev   = '{:02x}'.format(code.UpdateRevision)
                date  = '{:04x}'.format(code.Date & 0xffff) + '/' + '{:02x}'.format(code.Date >> 24 & 0xff) + '/' + '{:02x}'.format(code.Date >> 16 & 0xff)
                print("  " + cpuid + "\t: rev=" + rev + "\tdate=" + date)

            bios.replace("UPDATE0", microcodeimage.image)
            filename = args[1] + ".updated"
            bios.saveAs(filename)
            print('')
            print('new bios saved as ' + filename)

        print('--------------------------------')

    if doDump:
        bios.volumeDir.save(True)
        bios.saveModules()
        print('modules saved')

if __name__ == '__main__':
    main()
