import cStringIO as StringIO
import numpy as np
import byw.common.unwise_tiles as ut
import byw.common.touchspot as tspot
import astropy.io.fits as aif
import astropy.wcs as awcs

path = "unwise/data/timeresolved"

# TODO: use the good headers
def cutout(fitsfileobj,ra,dec,size,fits=False):
    hdul = aif.open(fitsfileobj)

    wcs = awcs.WCS(hdul[0].header)

    px,py = wcs.wcs_world2pix(np.array([[ra,dec]]),0)[0]

    bot = int(py)-int(size/2)
    left = int(px)-int(size/2)
    
    cut = hdul[0].data[max(bot,0):min(int(py)+int(size/2)+1,2048),
                       max(left,0):min(int(px)+int(size/2)+1,2048)]

    # Convert to fits
    if fits:
        # TODO: fitsiness, WCS header, etc.. Astropy doesn't support it w/ cutout
        cutf = aif.PrimaryHDU(cut)
        cutf.header["NAXIS"] = 2
        cutf.header["NAXIS1"] = cut.shape[1] # X, RA
        cutf.header["NAXIS2"] = cut.shape[0] # Y, Dec
        cutf.header["CTYPE1"] = "RA---TAN"
        cutf.header["CTYPE2"] = "DEC--TAN"
        cutf.header["CRVAL1"] = ra
        cutf.header["CRVAL2"] = dec
        cpx = min(px,int(size/2)
                  # Preserve fractional pixel value
                  +(px-int(px)))
        cpy = min(py,int(size/2)
                  # Preserve fractional pixel value
                  +(py-int(py)))
        cutf.header["CRPIX1"] = cpx+1 # Fits counts px starting at 1
        cutf.header["CRPIX2"] = cpy+1 # Fits counts px starting at 1
        cutf.header["CD1_1"] = hdul[0].header["CD1_1"] 
        cutf.header["CD1_2"] = hdul[0].header["CD1_2"]
        cutf.header["CD2_1"] = hdul[0].header["CD2_1"]
        cutf.header["CD2_2"] = hdul[0].header["CD2_2"]
        sio = StringIO.StringIO()
        cutf.writeto(sio)
        sio.seek(0)
        return sio.getvalue()
        
    return cut

import byw.common.imcache as imcache
cache = imcache.imcache(32)

def get_by_tile_epoch(*args,**kwargs):
    return cache(_get_by_tile_epoch,*args,**kwargs)
def _get_by_tile_epoch(coadd_id,epoch_num,ra,dec,band,size=None,fits=False):
    # Build the URL
    path_ = "/".join(
        (path,
         "e%03d"%int(epoch_num), # epoch in e### form
         coadd_id[:3], # first 3 digits of RA
         coadd_id, # the tile name itself
         "unwise-%s-w%d-img-m.fits"%(coadd_id,band)))


    # Get content from S3
    sio = StringIO.StringIO()
    tspot.bucket.download_fileobj(path_,sio)
    sio.seek(0)

    # Perform cutouts if size is specified
    if size is not None:
        return cutout(sio,ra,dec,size,fits=fits)
    
    return sio.getvalue()


def get(ra,dec,band,picker=lambda x: True,size=None,fits=False):
    """
    Download tiles by ra, dec, and date range.
    If size is None, return full tiles. Otherwise, cut tiles
    to fit.
    """
    tiles = []
    
    # For all tiles covering RA, Dec position
    bandcnt = [0,0]
    for _,tile,epochs in ut.get_tiles(ra,dec):

        # For all epochs covered by given date range
        for i in xrange(len(epochs.data)):
            e = epochs.data[i]

            if e["BAND"] == 1:
                i = bandcnt[0]
                bandcnt[0] += 1
            elif e["BAND"] == 2:
                i = bandcnt[1]
                bandcnt[1] += 1
            else:
                raise Exception("Invalid band %d"%e["BAND"])

            # Filter epochs by picker
            if not picker(e,i): continue
            
            tiles.append(get_by_tile_epoch(tile["COADD_ID"],e["EPOCH"],
                                           ra,dec,band,size=size,fits=fits))
    
    return tiles


def get_by_mjd(ra,dec,band,start_mjd=0,end_mjd=2**23,size=None,fits=False):
    """Get tiles with epochs within supplied date range"""
    return get(ra,dec,band,
               picker=lambda e,i: (band == e["BAND"] and
                                   not (end_mjd <= e["MJDMIN"] or
                                        start_mjd >= e["MJDMAX"])),
               size=size,fits=fits)


def get_by_epoch_order(ra,dec,band,epochs,size=None,fits=False):
    """
    Return tiles with epochs within the order supplied.
    For example, epochs = (0,1) will return the first 2 epochs
    in which the tile appeared, regardless of whether the unwise
    epoch numbering is e000 and e001
    """
    return get(ra,dec,band,
               picker=lambda e,i: (band == e["BAND"] and i in epochs),
               size=size,fits=fits)


def get_by_epoch_name(ra,dec,band,epochs,size=None,fits=False):
    """
    Return tiles with epoch names as supplied, like "e000"
    """
    return get(ra,dec,band,
               picker=lambda e,i: (band == e["BAND"] and
                                   ("e%03d"%(e["epoch"])) in epochs),
               size=size,fits=fits)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ra",type=float)
    ap.add_argument("dec",type=float)
    ap.add_argument("band",type=int,choices=(1,2))
    ap.add_argument("epoch",type=int)
    ap.add_argument("--size",default=None,type=int)
    args = ap.parse_args()

    #tiles = get_by_mjd(args.ra,args.dec,args.band,args.start_mjd,args.end_mjd)
    tiles = get_by_epoch_order(args.ra,args.dec,args.band,epochs=(args.epoch,),size=args.size,fits=True)
    import sys
    sys.stdout.write(tiles[0])

    
if __name__ == "__main__": main()
