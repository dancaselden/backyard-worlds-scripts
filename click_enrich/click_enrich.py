from astropy.io import fits
from astroquery.simbad import Simbad
import astropy.coordinates as coord
import astropy.units as u

#TODO: pull out into helper lib
def set_votable_fields(fields=None):
    # astroquery is pretty wonky... if you clear all
    #   fields, it throws an error and resets them:
    # Simbad.remove_votable_fields(*Simbad.get_votable_fields())
    #   causes an error
    if fields is None:
        fields = set(('ra','dec','pmra','pmdec'))
    if not isinstance(fields,set):
        try:
            fields = set(fields)
        except Exception,e:
            sys.std.err.write("set_votable_fields needs a set "+
                              "of fields, or a datatype that "+
                              "can be converted to a set")
            raise e
    # Format fields for backyard worlds common use
    if 'ra' in fields:
        fields.remove('ra')
        fields.add('ra(2;A;FK5;J2000;2000)')
    if 'dec' in fields:
        fields.remove('dec')
        fields.add('dec(2;D;FK5;J2000;2000)')
    # Duplicates are possible, so reset to their default
    Simbad.reset_votable_fields()
    # Capture original fields
    old_fields = set(Simbad.get_votable_fields())
    # Add all fields first (so we don't empty it and trigger
    #   their wonky error
    # Add fields in the new fields but not yet in the old_fields
    Simbad.add_votable_fields(*(fields-old_fields))
    # Then remove fields in the old_fields set that are not
    #   present in the new fields set
    Simbad.remove_votable_fields(*(old_fields-fields))


def enrich_click(args):
    idx,ra,de = args
    # Build SkyCoord object for Simbad query
    c = coord.SkyCoord(ra,de,frame="fk5",unit="deg")
    # Try 10 times in case of timeout
    for i in xrange(10):
        try:
            # Query Simbad for region around SkyCoord c w/ radius
            r = Simbad.query_region(c, radius='0d0m30s')
            break
        except requests.exceptions.ConnectionError,e:
            sys.stderr.write("Error connecting with query %s\n"%str(c))

    if r is not None:
        # Object found in simbad
        # Calculate total PM as:
        # (pmra^2 + pmde^2) ^ (1/2)
        pmra = r[0][r.index_column("PMRA")]
        pmdec = r[0][r.index_column("PMDEC")]
        if ((hasattr(pmra,"mask") and pmra.mask) or
            (hasattr(pmdec,"mask") and pmdec.mask)):
            # One or more not available
            pm = ""
        else:
            pm = ((pmra**2)+(pmdec**2))**(0.5)
        # Calculate distance
        # Supposedly Simbad can do this with the "distance"
        #   field, but it seems to be usually empty? Maybe
        #   "distance" refers to 3d distance?
        ra = r[0][r.index_column("RA_2_A_FK5_J2000_2000")]
        dec = r[0][r.index_column("DEC_2_D_FK5_J2000_2000")]
        c2 = coord.SkyCoord(ra,dec,frame="fk5",unit=(u.hourangle, u.deg))
        sep = c.separation(c2)
        return (idx,str(pm),
                sep.to_string(unit=u.deg,decimal=False),
                r[0][r.index_column("OTYPE")])
    return (idx,)
def _work(row):
    return enrich_click(row)
def main():
    import os
    import argparse
    import multiprocessing
    ap = argparse.ArgumentParser(description="Enrich click data with Simbad fields. "+
                                 "Takes click data as FITS file")
    ap.add_argument("file",type=str,
                    help="Path to FITS file with click data")
    ap.add_argument("--outfile",type=str,required=False,
                    help="Where to write results")
    ap.add_argument("--batchsize",type=int,default="1000")
    ap.add_argument("--maxprocs",type=int,default=8)
    ap.add_argument("--skipto",type=int,default=0)
    ap.add_argument("--runto",type=int,default=None)
    args = ap.parse_args()
    if args.outfile == "" or args.outfile is None:
        b,e = os.path.splitext(args.file)
        ofname = "%s_processed.csv"%(b)
    else:
        ofname = args.outfile
    # TODO: no need to do this in each proc, but also need to guarantee
    #       it happens before enrich is called for non main() users
    # Tell Simbad which fields to grab (e.g., 'coordinates', 'pm')
    set_votable_fields(["ra","dec","pmra","pmdec","otype"])
    # Turn off Simbad empty warnings
    import warnings
    warnings.filterwarnings('ignore',category=UserWarning, append=True)
    f = fits.open(args.file,memmap=True)
    p = multiprocessing.Pool(args.maxprocs)
    if args.runto is None:
        runto = len(f[1].data)
    else:
        runto = args.runto
    assert(args.skipto < runto)
    for i in xrange(args.skipto,len(f[1].data),args.batchsize):
        print "*"*40
        print "Running:",i
        print "*"*40
        batch = f[1].data[i:i+args.batchsize]
        # Serious memory errors using FITS rows with astro types
        #   in multiprocessing... still need to debug (<= TODO: )
        # Just pass in the index, RA,DE
        r2 = []
        for j in xrange(len(batch)):
            r2.append((j,float(batch[j][13]),float(batch[j][14])))
        res = p.map(_work,r2)
        del r2
        ofile = open(ofname,'ab')
        for retval in res:
            ofile.write(','.join([str(i) for i in batch[retval[0]]]))
            if len(retval) > 1:
                ofile.write(',')
                ofile.write(','.join(retval[1:]))
            ofile.write('\n')
        ofile.close()

if __name__ == "__main__":
    main()
