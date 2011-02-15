#!/usr/bin/env python
# Copyright (c) 2010 Citrix Systems, Inc. All use and distribution of this
# copyrighted material is governed by and subject to terms and conditions
# as licensed by Citrix Systems, Inc. All other rights reserved.
# Xen, XenSource and XenEnterprise are either registered trademarks or
# trademarks of Citrix Systems, Inc. in the United States and/or other 
# countries.

import os.path
import subprocess

class PCIIds:
    def __init__(self, fn):
        self.vendor_dict = {}
        self.sub_dict = {}
        self.main_dict = {}
        self.class_dict = {}
        
        vendor = None
        cls = None

        fh = open(fn)
        for l in fh:
            line = l.rstrip()
            if line == '' or line.startswith('#'): continue

            if line.startswith('C'):
                # Class
                vendor = None
                _, cls, cls_text = line.split(None, 2)
                if cls not in self.class_dict:
                    self.class_dict[cls] = (cls_text, None)
            elif line.startswith('\t\t'):
                if vendor:
                    # subvendor, subdevice
                    subvendor, subdevice, text = line.split(None, 2)
                    key = "%s:%s" % (subvendor, subdevice)
                    if key not in self.sub_dict:
                        self.sub_dict[key] = text
            elif line.startswith('\t'):
                if vendor:
                    # device
                    device, text = line.split(None, 1)
                    key = "%s:%s" % (vendor, device)
                    if key not in self.main_dict:
                        self.main_dict[key] = text
                else:
                    # subclass
                    sub_cls, sub_text = line.split(None, 1)
                    key = "%s:%s" % (cls, sub_cls)
                    if key not in self.class_dict:
                        self.class_dict[key] = (cls_text, sub_text)
            else:
                # vendor
                cls = None
                vendor, text = line.split(None, 1)
                if vendor not in self.vendor_dict:
                    self.vendor_dict[vendor] = text
    
        fh.close()

    @classmethod
    def read(cls):
        for f in ['/usr/share/hwdata/pci.ids']:
            if os.path.exists(f):
                return cls(f)
        raise Exception, 'Failed to open PCI database'

    def findVendor(self, vendor):
        return vendor in self.vendor_dict and self.vendor_dict[vendor] or None

    def findDevice(self, vendor, device):
        key = "%s:%s" % (vendor, device)
        return key in self.main_dict and self.main_dict[key] or None

    def findSubdevice(self, subvendor, subdevice):
        key = "%s:%s" % (subvendor, subdevice)
        return key in self.sub_dict and self.sub_dict[key] or None

    def lookupClass(self, cls_str):
        ret = []
        for k, (c, sc) in self.class_dict.items():
            if not sc and cls_str in c and k not in ret:
                ret.append(k)
        return ret

class PCIDevices:
    def __init__(self):
        self.devs = {}
        
        cmd = subprocess.Popen(['lspci', '-mn'], bufsize = 1, stdout = subprocess.PIPE)
        for l in cmd.stdout:
            line = l.rstrip()
            el = filter(lambda x: not x.startswith('-'), line.replace('"','').split())
            self.devs[el[0]] = {'id': el[0], 'class': el[1][:2], 'subclass': el[1][2:], 'vendor': el[2], 'device': el[3]}
            if len(el) == 6:
                self.devs[el[0]]['subvendor'] = el[4]
                self.devs[el[0]]['subdevice'] = el[5]
        cmd.wait()

    def findByClass(self, cls, subcls = None):
        """ return all devices that match either of:

        	class, subclass
        	[class1, class2, ... classN]"""
        if subcls:
            assert isinstance(cls, str)
            return filter(lambda x: x['class'] == cls and x['subclass'] == subcls, self.devs.values())
        else:
            assert isinstance(cls, list)
            return filter(lambda x: x['class'] in cls, self.devs.values())

    def findRelatedFunctions(self, dev):
        """ return other devices that share the same bus & slot"""
        def slot(dev):
            left, _ = dev.rsplit('.', 1)
            return left

        return filter(lambda x: x != dev and slot(x) == slot(dev), self.devs.keys())


if __name__ == "__main__":
    ids = PCIIds.read()
    video_class = ids.lookupClass('Display controller')

    devs = PCIDevices()
    for video_dev in devs.findByClass(video_class):
        print video_dev['id'], ids.findVendor(video_dev['vendor']), \
        ids.findDevice(video_dev['vendor'], video_dev['device'])
        print devs.findRelatedFunctions(video_dev['id'])
    print devs.findRelatedFunctions('00:1d.1')


