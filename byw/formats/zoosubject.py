"""
Zooniverse Subject format reader
"""
import collections

ZooSubjectHeader = "subject_id,project_id,workflow_id,subject_set_id,metadata,locations,classifications_count,retired_at,retirement_reason"
ZooSubject = collections.namedtuple("ZooSubject",ZooSubjectHeader)

class ZooSubjectReader:
    def __init__(self,fname):
        self.fname = fname
        self.f = open(self.fname,'rb')
        # Skip header
        l = self.f.readline()
        if l.strip() != ZooSubjectHeader:
            raise Exception("%s is not in %s format"%(self.fname,
                                                      self.__class__.__name__))
        
    def readline(self):
        l = self.f.readline()
        if not l:
            return None
        # Deal with extra double-quotes in json elements
        l = l.replace('""','"')
        r = []
        # Split up to the JSON
        ofs = 0
        for i in xrange(4):
            ofs2 = l.find(",",ofs)
            if ofs2 == -1:
                raise Exception("%s is not in %s format"%(self.fname,
                                                          self.__class__.__name__))
            r.append(l[ofs:ofs2])
            ofs = ofs2+1
        # Extract metadata JSON
        ofs2 = l.find('}",',ofs)
        r.append(l[ofs+1:ofs2+1])
        ofs = ofs2+3
        # Extract locations JSON
        ofs2 = l.find('}",',ofs)
        r.append(l[ofs+1:ofs2+1])
        ofs = ofs2+3
        # classifications_count
        ofs2 = l.find(',',ofs)
        r.append(l[ofs:ofs2])
        ofs = ofs2+1
        # retired at
        ofs2 = l.find(',',ofs)
        r.append(l[ofs:ofs2])
        ofs = ofs2+1
        # retirement_reason
        ofs2 = l.find(',',ofs)
        r.append(l[ofs:ofs2])
        ofs = ofs2+1
        return ZooSubject(*r)

def main():
    import sys
    print "Testing ZooSubject"
    rdr = ZooSubjectReader(sys.argv[1])
    for i in xrange(10):
        r = rdr.readline()
        print r

if __name__ == "__main__":
    main()
