import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import numpy as np
import astropy.table as at
from cStringIO import StringIO
import astropy.io.fits as aif
import astropy.wcs as awcs
from astropy.stats import sigma_clipped_stats
from photutils import DAOStarFinder
import statsmodels.api as sm
from statsmodels.sandbox.regression.predstd import wls_prediction_std

import byw.common.angsep as angsep
import byw.common.api_consumer as api


def _detect_sources(cutout):
    """
    Detect sources in given fits image
    
    Image should already be background subtracted
    """
    im = aif.getdata(StringIO(cutout))

    mean, median, std = sigma_clipped_stats(im, sigma=3.0, iters=5)

    daofind = DAOStarFinder(fwhm=3.0, threshold=3.*std)

    return daofind(im)


def organize_coadds(coadds):
    """Organize coadds into a table & group by mjdmean"""
    # Build table
    res = at.Table(rows=[(np.int16(c["band"]),
                          np.int16(c["epoch"]),
                          np.float64(c["mjdmean"]),
                          0,) # Parallax group TBD
                         for c in coadds["epochs"]],
                   names=("band","epoch","mjdmean",
                          "parallax_group"),
                   dtype=("u2","u2","f8","u2"))

    # Group by mjdmean
    first_mjdmean = res[0]["mjdmean"] # Pick any coadd
    
    for coadd in res:
        # Test within 180 days of first
        diff = (coadd["mjdmean"] - first_mjdmean) % 365.
        if diff < 90 or diff > (365-90):
            coadd["parallax_group"] = 0
        else:
            coadd["parallax_group"] = 1

    return res


def fetch_cutouts(coadds,ra,dec,size):
    """Add cutouts to coadds table"""
    cutouts = []
    for coadd in coadds:
        cutouts.append(api.get_cutout(ra,dec,size,
                                      coadd["band"],coadd["epoch"]))
    coadds.add_column(at.Column(cutouts,name="cutout",dtype="object"))

    return coadds


def detect_sources(coadds):
    """
    Detect sources in cutouts from coadds table.
    
    Return list of detected sources w/ info, like band, from coadds tbl
    """
    sources = []
    for i in xrange(len(coadds)):
        coadd = coadds[i]
        #if coadd["parallax_group"] != 1: continue
        # Get the sources
        tbl = _detect_sources(coadd["cutout"])

        # Build WCS from SCAMP solution in cutout header
        wcs = awcs.WCS(aif.open(StringIO(coadd["cutout"]))[0])

        ras,decs = [],[]
        for source in tbl:
            # Use SCAMP solutions to convert px/py into RA/Dec
            ra,dec = wcs.wcs_pix2world(np.array([[
                source["xcentroid"],source["ycentroid"]
            ]]),0)[0]
            
            ras.append(ra); decs.append(dec)
            
        tbl.add_columns([at.Column([coadd["band"]]*len(tbl),
                                   name="band"),
                         at.Column([coadd["parallax_group"]]*len(tbl),
                                   name="parallax_group"),
                         at.Column(ras,name="ra"),
                         at.Column(decs,name="dec"),
                         at.Column([coadd["mjdmean"]]*len(tbl),
                                   name="mjdmean"),
                         at.Column([-1]*len(tbl),
                                   name="group"),
                         at.Column([i]*len(tbl),
                                   name="coadd")])
        sources.append(tbl)
    
    return at.vstack(sources)


def group_sources(sources):
    """Group sources by proximity"""
    # Match the sources through epochs across bands and parallax-groups
    # TODO: Also consider clustery clustercluster
    # For now, bin by closest. It doesn't take into account
    #   consistent magnitudes, shapes, colors, or anything,
    #   but it's a start...
    global_sources = [] 
    for i in xrange(len(sources)):
        source = sources[i]
        # Find membership in global sources
        for j in xrange(len(global_sources)):
            gs = global_sources[j]
            # TODO: For larger images, use haversine+balltree
            #if np.sqrt(((source["ra"] - gs[0]["ra"])**2)+
            #           ((source["dec"] - gs[0]["dec"])**2)) < 2:
            if angsep.angsep(source["ra"],source["dec"],
                             gs[0]["ra"],gs[0]["dec"]) < (2.75*3)/3600.:
                # If within 2px, merge
                source["group"] = j
                gs.append(source)
                break
        else:
            # None found
            source["group"] = len(global_sources)
            global_sources.append([source])
    
    return sources


def measure_pm(sources):
    """Measure PM over groups of sources"""
    pms = []
    for i in xrange(np.max(sources["group"])+1):
        # Split sources by group
        group = sources[sources["group"] == i]

        # h/t delta32
        # make the design matrix
        mjd = group["mjdmean"]
        A = np.matrix([np.ones(np.shape(mjd)),mjd]).T

        # OLS for RA
        b = group["ra"]

        fit_x = sm.OLS(b, A).fit()

        # OLS for Dec
        b = group["dec"]

        fit_y = sm.OLS(b, A).fit()

        pms.append((i,fit_x.params[1]*3600*1000*365.2422,fit_y.params[1]*3600*1000*365.2422))
        
    return at.Table(rows=pms,names=("group","pmra","pmdec"))


def get_pms(ra,dec,size):
    """
    Takes RA, Dec (degrees, decimal)

    Returns tables of the coadds, detected sources, and proper motion measurements
    """
        # Get tiles
    tiles = api.list_tiles(ra,dec)

    # Just take the best one
    tile = tiles["tiles"][0]

    # TEMPORARY:
    # Debugging, just take a couple epoch for speed
    #tile["epochs"] = tile["epochs"][:4]

    # Coadds should already be sorted by mjdmean, but enforce here
    # This will prevent sorting a larger list of detected sources down the road
    tile["epochs"] = sorted(tile["epochs"],key=lambda x: x["mjdmean"])
    
    # Re-order coadds to split parallax-cancelling groups
    coadds = organize_coadds(tile)

    # Fetch cutouts
    coadds = fetch_cutouts(coadds,ra,dec,size)

    # Detect sources in cutouts
    sources = detect_sources(coadds)    

    # Group sources by proximity
    sources = group_sources(sources)
    
    # Measure PM across sources
    pms = measure_pm(sources)

    return coadds,sources,pms


def plot_sources(coadds,sources,path):
    """Plot sources over coadds in PDF"""
    pdf = PdfPages(path)
    # Build PDF
    cols = 3
    # Deduce # of rows
    rows = len(coadds)/cols
    if len(coadds)%cols != 0: rows += 1
    fig, farr = plt.subplots(rows,cols,
                             sharex="col",sharey="row")

    # Flatten array
    if len(farr) < len(coadds):
        farr = farr.reshape(len(farr)*cols)

    # Add coadds & overlay sources
    for i in xrange(len(coadds)):
        coadd = coadds[i]
        cut = aif.getdata(StringIO(coadd["cutout"]))

        farr[i].imshow(cut,origin="lower",aspect="equal",
                       interpolation="nearest",cmap="Greys")
        farr[i].set_title("band %d epoch %d"%(coadd["band"],coadd["epoch"]))
        srcs = sources[sources["coadd"] == i]
        farr[i].scatter(srcs["xcentroid"],srcs["ycentroid"],marker=".")

        for src in srcs:
            farr[i].annotate(
                src["group"],
                xy=(src["xcentroid"],src["ycentroid"]), xytext=(-10, 10),
                textcoords='offset points', ha='right', va='bottom',
                bbox=dict(boxstyle='round,pad=0.25', fc='yellow', alpha=0.5),
                arrowprops=dict(arrowstyle = '->', connectionstyle='arc3,rad=0'),
                fontsize=6)

    pdf.savefig(bbox_inches="tight")
    plt.close("all")
    """
    # List all proper motions
    if len(pms) != 0:
        txt = []
        for i in xrange(len(pms)):
            txt.append([str(k) for k in pms[i]])
        plt.table(cellText=txt,colLabels=("Group","Time Basis","pmRA (tot)","pmDec (tot)","pmRA","pmDec"),
                  loc="upper center")
        plt.axis("off")
        pdf.savefig(bbox_inches="tight")
        plt.close()
    """
    """
    # List all source positions and MJDMeans
    txt = []
    for i in xrange(len(global_sources)):
        for src in global_sources[i]:
            txt.append([str(i),str(src["mjdmean"]),str(src["ra"]),str(src["dec"])])
    plt.table(cellText=txt,colLabels=("Group","MJDMean","RA","Dec"),
              loc="upper center")
    plt.axis("off")
    pdf.savefig(bbox_inches="tight")
    plt.close()
    """
    
    pdf.close()
    


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ra",type=float)
    ap.add_argument("dec",type=float)
    #ap.add_argument("band",type=int,choices=(1,2))
    ap.add_argument("size",type=int)
    ap.add_argument("pdfpath",type=str)
    args = ap.parse_args()

    coadds,sources,pms = get_pms(args.ra,args.dec,args.size)
    
    print sources
    print pms
    
    plot_sources(coadds,sources,args.pdfpath)

    
if __name__ == "__main__": main()
    
