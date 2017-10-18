import math
import numpy as np
import astropy.table as at # need to do this first, or astropy will barf?
import astropy.io as aio
import sklearn.neighbors as skn

tile_tree = None
tile_table = None
# Units are degrees unless stated
tile_width = (  2048 # pixels
              * 2.75 # arcseconds per pixel
                ) / 3600.0 # arcseconds per degree
tile_corner_radius = math.sqrt((
    (tile_width/2.0) # Degrees from center to edge
    **2)*2) # Euclidean distance


class rdtree:
    def __init__(self,table):
        self.table = table
        x = np.array(np.deg2rad([self.table['dec'],self.table['ra']])).transpose()
        x = x.reshape(-1,2)
        self.rdtree = skn.BallTree(
            x,
            metric="haversine",
        )

    def query_radius(self,ra,de,sep):        
        ra,de,sep = np.deg2rad(ra),np.deg2rad(de),np.deg2rad(sep)
        # TODO: all at once?
        x = np.array([[de,ra]])
        return self.rdtree.query_radius(x,sep,return_distance=True)


def __init(atlas):
    """Initialize the global tile tree and table from CSV"""
    global tile_tree, tile_table
    
    # Read tile descriptions from disk
    tile_table = aio.ascii.Csv().read(atlas)

    # Build global tile tree
    tile_tree = rdtree(tile_table)


def get_tiles(ra,dec):
    # First, get all tiles that *could* hold the position,
    # by radius    
    nearby_tiles = tile_tree.query_radius(ra,dec,tile_corner_radius)
    
    # Test actually within tiles, and capture shortest distance
    # to nearest edge
    within_tiles = []
    for tileofs in nearby_tiles[0][0]:
        tile = tile_table[tileofs]
        # Within declination
        # Top
        d = tile["dec"]+(tile_width/2.0) - dec
        if d < 0: continue
        nearest_edge = d

        # Bot
        d = dec - (tile["dec"]-(tile_width/2.0))
        if d < 0: continue
        nearest_edge = min(d,nearest_edge)
        
        #Within RA
        cosd = np.cos(np.deg2rad(dec))
        # Left
        d = tile["ra"]+((tile_width/2.0)/cosd) - ra
        if d < 0: continue
        # Convert RA Separation to Angular
        d = d
        nearest_edge = min(d,nearest_edge)
        
        # Left
        d = ra - (tile["ra"]-((tile_width/2.0)/cosd))
        if d < 0: continue
        # Convert RA Separation to Angular
        d = d
        nearest_edge = min(d,nearest_edge)

        within_tiles.append((nearest_edge,tile))

    # Sort by furthest from an edge. This is a better metric than
    # distance to tile center, because it accurately expresses
    # how complete the cutout will be in the corners versus edges
    return sorted(within_tiles,key=lambda x: x[0], reverse=True)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ra")
    ap.add_argument("dec")
    ap.add_argument("--atlas",default="allsky-atlas.csv")
    args = ap.parse_args()

    __init(args.atlas)

    for _,tile in get_tiles(float(args.ra),float(args.dec)):
        print tile["tile"]
    
if __name__ == "__main__": main()
else: __init("allsky-atlas.csv")
