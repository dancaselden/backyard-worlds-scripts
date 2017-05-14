"""
Ugh. its not really a tree, now, is it?

Could do KDtree, but the RA-wrapping would need thinking.
I'd love to use astropy's kdtree, but skycoords are
extremely slow. unfortunately, so slow that the algorithmic
improvement from a kdtree probably wouldn't overcome the linear slowdown
- Instead, sort by declination. 
"""

import collections
import bisect
import numpy as np

BBox = collections.namedtuple("BBox","entry,raleft,raright,debot,detop")
Point = collections.namedtuple("Point","entry,ra,de")

# Handle rolling over boundaries
def ra_(ra):
    if 0 > ra or ra > 360:
        return ra%360.0
    return ra

def BBox_new_subject(subj):
    """Return a BBox given a Subject"""
    pic_angle = 0.0975
    # Get bottom-left point, adjusting RA
    ra = float(subj.ra)
    de = float(subj.de)
    raofs = (pic_angle/np.cos(np.deg2rad(de)))
    # Extract ra,dec from bottom-left and top-right, and get rid
    #   of astropy coordinates, to make a fast bounding box
    return BBox(subj,
                ra_(ra+raofs),ra_(ra-raofs),
                de-pic_angle,de+pic_angle)

class radeboxes(list):
    def __init__(self,*args,**kwargs):
        tmp = list(*args,**kwargs)
        for o in tmp:
            self.add(o)
    def add(self,o):
        # Wrap w/ bottom de
        bisect.insort(self,(o.detop,o))
    def in_objs(self,o):
        objs = []
        o = (float(o.de),o)
        if o[0] < -90:
            raise Exception("Invalid declination %d"%(o[0]))
        # Find left-most position
        idx = bisect.bisect_left(self,o)
        for i in xrange(idx,len(self)):
            bb = self[i]
            if o[0] < bb[1].debot:
                break
            if self.point_in_bb(bb[1],o[1]):
                objs.append(bb[1])
        return objs
    def point_in_bb(self,bb,s):
        # TODO: be an adult and ~binsearch this
        # Test if subj between raleft and raright
        sra = float(s.ra)
        if bb.raleft < bb.raright:
            # RA spans 0
            if not ((bb.raleft >= sra and
                     sra >= 0) or
                    (360 >= sra and
                     sra >= bb.raright)):
                return False
        else:
            if not (bb.raleft >= sra and
                    sra >= bb.raright):
                return False
        sde = float(s.de)
        # Test if subj between debot and detop
        if (bb.debot < -90 or bb.debot > 90 or
            bb.detop < -90 or bb.detop > 90):
            # DE spans 0
            raise Exception("Bounding box covers a pole. Do I look like an astronomer?\n%s\n%s"%(bb,s))
        else:
            if not (bb.debot <= sde and
                    sde <= bb.detop):
                return False
        return True

"""
BCircle = collections.namedtuple("BCircle","entry,ra,de,radius")
class radecircles(list):
    def __init__(self,*args,**kwargs):
        tmp = list(*args,**kwargs)
        self.radius = None
        for o in tmp:
            self.add(o)
    def add(self,o):
        # All circles must have the same radius
        if self.radius != None:
            if self.radius != o.radius:
                raise Exception("All BCircles must have the same radius")
        else:
            self.radius = o.radius
        # Wrap w/ bottom de
        bisect.insort(self,(float(o.de)+o.radius,o))
    def in_objs(self,o):
        objs = []
        o = (float(o.de),o)
        if o[0] < -90:
            raise Exception("Bounding box covers a pole. Do I look like an astronomer?\n%s\n%s"%(bd,s))
        # find left-most position
        idx = bisect.bisect_left(self,o)
        # search until point exceeds top of the circle
        for i in xrange(idx,len(self)):
            bd = self[i]
            # Slide up circles until bottom of circle doesn't cover
            # the point
            if o[0] < (float(bd[1].de) - bd[1].radius):
                break
            if self.point_in_bc(bd[1],o[1]):
                objs.append(bds
"""
