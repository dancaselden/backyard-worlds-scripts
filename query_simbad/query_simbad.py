from astroquery.simbad import Simbad
import astropy.coordinates as coord
import astropy.units as u
import sys
import os

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
def process_sheet(ifname, ofname, radius):
    # Tell Simbad which fields to grab (e.g., 'coordinates', 'pm')
    set_votable_fields(["ra","dec","pmra","pmdec","otype"])
    # Read CSV file, taking file name from cmdline
    csv = open(ifname,'rb').read()
    # Split by line
    csv = csv.split('\n')
    # Strip off extra whitespace (if any)
    last_col = 0
    objs = [None]*len(csv)
    # For each row:
    for i in xrange(len(csv)):
        csv[i] = csv[i].strip()
        csv[i] = csv[i].split(',')
        # Get one row
        r = csv[i]
        # Track the right-most col to not destroy
        #   anyone's existing columns later
        if len(r) > last_col: last_col = len(r)
        # If not 4 columns, something wonky. Skip row
        if len(r) < 4: continue
        ra, de = r[2],r[3]
        try:
            # If value can't convert to float,
            #   something wonky. Skip row
            ra = float(ra)
            de = float(de)
        except ValueError,e:
            # (skipping row)
            continue
        # Build SkyCoord object for Simbad query
        c = coord.SkyCoord(ra,de,frame="fk5",unit="deg")
        # Query Simbad for region around SkyCoord c w/ radius
        r = Simbad.query_region(c, radius=radius)
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
            objs[i] = (str(pm),sep.to_string(unit=u.deg,decimal=False),
                       r[0][r.index_column("OTYPE")])
    # Write out new csv with fields from Simbad
    # Since every csv is different, let's tack this on as
    #   the rightmost column to ensure we don't destroy
    #   anyone's format
    if ofname == "-":
        of = sys.stdout
    else:
        of = open(ofname,'wb')
    for i in xrange(len(csv)):
        while len(csv[i]) < last_col:
            csv[i].append('')
        if objs[i] is not None:
            csv[i].extend(objs[i])
        of.write(','.join(csv[i]))
        of.write('\n')
    if ofname != "-":
        of.close()

# Each worker will run this _work function
def _work(args):
    fname,radius = args
    b,e = os.path.splitext(fname)
    ofname = "%s_processed%s"%(b,e)
    process_sheet(fname,ofname,radius)

def main():
    import argparse
    import multiprocessing
    MAX_PROCS=8
    # Describe valid arguments & program usage
    ap = argparse.ArgumentParser(description="Lookup Simbad entries for RA DE in CSV file and "+
                                 "write a new file with an added column containing 'N' if there "+
                                 "were no entries. RA/DE is assumed 3rd&4th col, in degrees FK5 "+
                                 "J2000. Processed files will be written to <filepath>_processed"+
                                 ".<extension>")
    ap.add_argument("--radius",default="0d0m10s",
                    help="Radius within which to search Simbad. Must be in form "+
                    "1d2m3s")
    ap.add_argument("files",nargs="+",type=str,
                    help="CSV files to process")
    args = ap.parse_args()
    wargs = [(fn,args.radius) for fn in args.files]
    if len(args.files) > 0: # should be...
        # Create a pool of a bunch of workers
        p = multiprocessing.Pool(MAX_PROCS)
        # Launch pool of workers against files argument
        p.map(_work,wargs)

if __name__ == "__main__":
    main()

