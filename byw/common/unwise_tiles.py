import math
import numpy as np
import astropy.table as at # need to do this first, or astropy will barf?
import astropy.io as aio
import sklearn.neighbors as skn
import astropy.wcs as awcs
import astropy.io.fits as aif


# Units are degrees unless stated
tile_width = (  2048 # pixels
              * 2.75 # arcseconds per pixel
                ) / 3600.0 # arcseconds per degree
tile_corner_radius = math.sqrt((
    (tile_width/2.0) # Degrees from center to edge
    **2)*2) # Euclidean distance


tile_tree = None
tr_atlas = None


class rdtree:
    def __init__(self,table):
        self.table = table
        x = np.array(np.deg2rad([self.table["DEC"],self.table["RA"]])).transpose()
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
    """
    Initialize the global tile tree and table from CSV,
    and the tile & date -> epoch list from CSV

    !!epoch list must be sorted by tilename then epoch!!
    sort tr.csv -t ',' -k 1,4 > tr_sorted.csv
    """
    global tile_tree, tr_atlas

    # Initialize atlas
    tr_atlas = aif.open(atlas)

    # Build global tile tree
    tile_tree = rdtree(tr_atlas[1].data)


def _tile_contains_position(tile,ra,dec):
    """
    Test whether tile contains position.
    Return summed distance to nearest edges, epochs if contained
    Return None,epochs if not contained
    """
    # Get a WCS
    epochs = get_epochs(tile)
    wcs = awcs.WCS(epochs.header)

    # Find pixel coordinates of ra, dec
    px,py = wcs.wcs_world2pix(np.array([[ra,dec]]),0)[0]

    # Calculate sum of distance to two closest edges
    if px > 1024.5: px = 2048-px
    if py > 1024.5: py = 2048-py

    # Don't return tiles not containing position or
    # with very small cutouts
    if px <= 1 or py <= 1: return None,None
    
    return px+py,epochs
    
def get_tiles(ra,dec):
    """
    Get tiles containing ra, dec

    Sort by furthest from edges, and find epochs (and WCS template)

    Returns sum distance to nearest 2 edges, tile, epochs
    """
    # First, get all tiles that *could* hold the position,
    # by radius    
    nearby_tiles = tile_tree.query_radius(ra,dec,tile_corner_radius)
    
    # Test actually within tiles, and capture shortest distance
    # to nearest edge
    within_tiles = []
    for tileofs in nearby_tiles[0][0]:
        tile = tr_atlas[1].data[tileofs]
        nearest_edge,epochs = _tile_contains_position(tile,ra,dec)
        if nearest_edge is not None:
            within_tiles.append((nearest_edge,tile,epochs))

    # Sort by furthest from an edge. This is a better metric than
    # distance to tile center, because it accurately expresses
    # how complete the cutout will be in the corners versus edges
    return sorted(within_tiles,key=lambda x: x[0], reverse=True)


def get_epochs(tile):
    """Get all epochs of given tile"""
    return tr_atlas[tile["IDX"]]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ra",type=float)
    ap.add_argument("dec",type=float)
    ap.add_argument("--atlas",default="tr_atlas.fits")
    args = ap.parse_args()

    __init(args.atlas)

    for _,tile,epochs in get_tiles(float(args.ra),float(args.dec)):
        print tile["COADD_ID"],
        for e in epochs.data:
            print e,
        print


if __name__ == "__main__": main()
else: __init("tr_atlas.fits")