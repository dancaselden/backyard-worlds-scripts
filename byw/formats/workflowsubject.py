"""
Workflow subject format reader
"""
import collections

WorkflowSubjectHeader = "workflow_id,subject_id,ra,de"
WorkflowSubject = collections.namedtuple("WorkflowSubject",WorkflowSubjectHeader)

class WorkflowSubjectReader:
    """""" 
    def __init__(self,fname):
        self.fname = fname
        self.f = open(self.fname,'rb')
        # Skip header
        l = self.f.readline()
        if l.strip() != WorkflowSubjectHeader:
            raise Exception("%s is not in %s format"%(self.fname,
                                                      self.__class__.__name__))

    def readline(self):
        l = self.f.readline()
        if not l:
            return None
        return WorkflowSubject(*l.strip().split(','))

    def __iter__(self):
        while True:
            o = self.readline()
            if not o: raise StopIteration
            yield o

def main():
    import sys
    print "Testing WorkflowSubject"
    rdr = WorkflowSubjectReader(sys.argv[1])
    for i in xrange(10):
        r = rdr.readline()
        print r

if __name__ == "__main__":
    main()
