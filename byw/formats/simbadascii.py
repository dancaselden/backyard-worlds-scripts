"""
Parse Simbad's default sim-coo ascii table
"""
import collections
import astropy.coordinates as coo
import astropy.units as u

SimbadEntryHeader = "ra,de,otype,sptype"
SimbadEntry = collections.namedtuple("SimbadEntry",SimbadEntryHeader)

class SimbadEntryReader:
    """""" 
    def __init__(self,fname):
        self.fname = fname
        self.f = open(self.fname,'rb')
        # Skip header
        l = self.f.readline()
        if l.strip() != SimbadEntryHeader:
            raise Exception("%s is not in %s format"%(self.fname,
                                                      self.__class__.__name__))

    def readline(self):
        l = self.f.readline()
        if not l:
            return None
        return SimbadEntry(*l.strip().split(','))

    def __iter__(self):
        while True:
            o = self.readline()
            if not o: raise StopIteration
            yield o

class SimbadAsciiReader:
    """"""
    def __init__(self,fname):
        self.fname = fname
        self.f = open(self.fname,'rb')
        # skip header
        while True:
            l = self.f.readline()
            if not l:
                raise Exception("%s is not in %s format"%(self.fname,
                                                          self.__class__.__name__))
            if l.startswith('-'):
                l = l.split('|')
                if len(l) == 12: break

    def readline(self):
        l = self.f.readline()
        if not l:
            return None
        if l.startswith('='):
            # hit footer
            return None
        r = l.split('|')
        # Convert ICRS HMS to FK5 degrees
        # Break out coord1 into ra,dec
        rade = r[3].strip().split(' ')
        c = coo.SkyCoord(':'.join(rade[:3]),':'.join(rade[3:]),unit=(u.hourangle,u.deg))
        c = c.fk5
        return SimbadEntry(c.ra.deg,c.dec.deg,
                           # Get rid of whitespace padding
                           r[2].strip(),r[9].strip())

    def __iter__(self):
        while True:
            o = self.readline()
            if not o: raise StopIteration
            yield o

def main():
    import sys
    print "Testing SimbadEntrys"
    rdr = SimbadEntryReader(sys.argv[1])
    for i in xrange(1):
        o = rdr.readline()
        if not o: break
        print o

if __name__ == "__main__":
    main()
