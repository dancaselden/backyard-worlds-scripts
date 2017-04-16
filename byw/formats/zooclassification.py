import collections
import re

ZooClassificationHeader=("classification_id,user_name,user_id,user_ip,workflow_id,"+
        "workflow_name,workflow_version,created_at,gold_standard,"+
        "expert,metadata,annotations,subject_data,subject_ids")
ZooClassification = collections.namedtuple("ZooClassification",ZooClassificationHeader)
class ZooClassificationReader:
    def __init__(self,fname):
        self.fname = fname
        self.f = open(self.fname,'rb')
        # skip header
        l = self.f.readline()
        if l == ZooClassificationHeader:
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
        for i in xrange(10):
            ofs2 = l.find(",",ofs)
            if ofs2 == -1:
                raise Exception("%s is not in %s format"%(self.fname,
                                                          self.__class__.__name__))
            r.append(l[ofs:ofs2])
            ofs = ofs2+1
        # Extract 2 JSON columns
        ofs2 = l.find('}",',ofs)
        r.append(l[ofs+1:ofs2+1])
        ofs = ofs2+4
        ofs2 = l.find(']",',ofs)
        r.append(l[ofs:ofs2+1])
        ofs = ofs2+4
        # Extract the last JSON column
        last_comma = l.rfind(',')
        r.append(l[ofs:last_comma-1])
        # and the final field, minus the newline
        r.append(l[last_comma+1:-1])
        
        if len(l) == 0:
            return None
        return ZooClassification(*r)

def main():
    import sys
    print "Testing classification reader"
    rdr = ZooClassificationReader(sys.argv[1])
    print rdr
    for i in xrange(10):
        print rdr.readline()
    

if __name__ == "__main__":
    main()
