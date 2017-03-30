from astroquery.simbad import Simbad
import astropy.coordinates as coord
import astropy.units as u
import sys
import os

def simbad_query_region(ra,de,radius):
    # Build coord object
    c = coord.SkyCoord(ra, de, unit="deg", frame="fk5")
    # Query region within radious 1arcmin around coord 
    return Simbad.query_region(c, radius=radius)
def process_sheet(ifname, ofname, radius):
    # Read CSV file, taking file name from cmdline
    csv = open(ifname,'rb').read()
    # Split by line
    csv = csv.split('\n')
    # Strip off extra whitespace (if any)
    last_col = 0
    no_objs = set()
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
        # Query simbad for existence
        if simbad_query_region(ra,de,radius) is None:
            # No object found in simbad
            no_objs.add(i)
    # Create a column for "N" when simbad query is empty
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
        csv[i].append('N') if i in no_objs else csv[i].append('')
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

