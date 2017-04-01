import sys
import requests
import json
import time
from astropy.io import fits

def get_pm(row):
    # Calculate total PM
    pmra = row[3].strip()
    pmde = row[4].strip()
    if (len(pmra) == 0 or len(pmde) == 0 or
        pmra == "~" or pmde == "~"):
        pm = ""
    else:
        pmra = float(row[3])
        pmde = float(row[4])
        pm = ((pmra**2)+(pmde**2))**(0.5)
    return pm

###
# Angsep
import numpy
import string
def angsep(ra1deg,dec1deg,ra2deg,dec2deg):
    """
    http://www.stsci.edu/~ferguson/software/pygoodsdist/pygoods/angsep.py
    From angsep.py Written by Enno Middelberg 2001

    Determine separation in degrees between two celestial objects 
    arguments are RA and Dec in decimal degrees. 
    """
    ra1rad=ra1deg*numpy.pi/180
    dec1rad=dec1deg*numpy.pi/180
    ra2rad=ra2deg*numpy.pi/180
    dec2rad=dec2deg*numpy.pi/180
    # calculate scalar product for determination
    # of angular separation
    x=numpy.cos(ra1rad)*numpy.cos(dec1rad)*numpy.cos(ra2rad)*numpy.cos(dec2rad)
    y=numpy.sin(ra1rad)*numpy.cos(dec1rad)*numpy.sin(ra2rad)*numpy.cos(dec2rad)
    z=numpy.sin(dec1rad)*numpy.sin(dec2rad)
    rad=numpy.arccos(x+y+z) # Sometimes gives warnings when coords match
    # use Pythargoras approximation if rad < 1 arcsec
    sep = numpy.choose(rad<0.000004848,(
        numpy.sqrt((numpy.cos(dec1rad)*(ra1rad-ra2rad))**2+(dec1rad-dec2rad)**2),rad))
    # Angular separation
    sep=sep*180/numpy.pi
    return sep
###

def get_sep(click,row):
    # Calculate angular separation
    ra1,de1 = click
    ra2,de2 = float(row[1]),float(row[2])
    return angsep(ra1,de1,ra2,de2)
def ask_simbad(clicks):
    global writelock, simbadlock, simbadtime, args, fitsdata
    cmds = [
        'output console=off script=off', # doesn't appear to be a way to disable errors
        'format object "%OTYPE|%COO(d;A)|%COO(d;D)|%PM(A)|%PM(D)"',
        'set limit 1',
    ]
    for ra,de in clicks:
        # Expecting iterable of (ra,de)
        cmds.append("echodata -")
        cmds.append("query coo %s %s radius=%s frame=FK5 equi=2000.0"%
                    (ra,de,"30.0s"))
    cmds = '\n'.join(cmds)
    data = {'script': cmds}
    simbadlock.acquire()
    cur = time.time()
    freq = 0.2
    if cur-simbadtime < freq: # Simbad says no more than 6 per sec
        sleep(freq - (cur-simbadtime))
    simbadtime = time.time()
    simbadlock.release()
    r = requests.post("http://simbad.u-strasbg.fr/simbad/sim-script?echo%20%3d%3d",
                      data=data)
    if r.status_code != 200:
        return r.status_code,r.text
    # Break off the data section from the response
    tok = "::data::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::"
    ofs = r.text.find(tok)
    if ofs < 0:
        return -1,r.text
    data = r.text[ofs+len(tok):].split('\n')
    return r.status_code,data
def query_clicks(clicks):
    global writelock, simbadlock, simbadtime, args, fitsdata
    # Query simbad and break apark results
    sc,data = ask_simbad(clicks)
    if sc != 200:
        return sc,data
    # For each row, calculate PM, angular separation,
    #   or track whether the row was empty
    res = []
    empty = False
    i = -1
    for row in data:
        if row == "":
            continue
        if row=="-":
            if empty:
                # No result for prev query
                res.append(None)
            empty = True
            i += 1
        else:
            row = row.split('|')
            pm = get_pm(row)
            sep = get_sep(clicks[i],row)
            res.append((str(sep),pm,row[0]))
            empty = False
    else:
        # Check if the last row had results
        if empty:
            res.append(None)
    return 200,res
def to_csv(of,batch,data):
    global writelock, simbadlock, simbadtime, args, fitsdata
    for i in xrange(len(batch)):
        of.write(','.join([str(x) for x in batch[i]]))
        if data[i] is not None:
            # No result, write line
            of.write(',')
            of.write(','.join([str(x) for x in data[i]]))
        else:
            # write empty cells
            of.write(',,,')
        of.write(',\n')
def work(idxs):
    global writelock, simbadlock, simbadtime, args, fitsdata
    print "*"*40,'\n',"Running:",idxs,'\n',"*"*40
    batch = fitsdata[idxs[0]:idxs[1]]
    clicks = []
    for i in xrange(len(batch)):
        clicks.append((batch[i][13],batch[i][14]))
    try:
        stat,data = query_clicks(clicks)
    except requests.exceptions.ConnectionError,e:
        idxs1 = (idxs[0],idxs[0]+((idxs[1]-idxs[0])/2))
        idxs2 = (idxs[0]+((idxs[1]-idxs[0])/2),idxs[1])
        print idxs,"broke. Splitting it in half and running again:",idxs1,idxs2
        work(idxs1)
        work(idxs2)
        return
    if stat != 200:
        print "Error:",txt
        return
    writelock.acquire()
    of = open(args.outfile,'ab')
    to_csv(of,batch,data)
    of.close()
    writelock.release()
def winit(writelock_, simbadlock_, simbadtime_, args_, fitsdata_):
    global writelock, simbadlock, simbadtime, args, fitsdata
    writelock = writelock_
    simbadlock = simbadlock_
    simbadtime = simbadtime_
    args = args_
    fitsdata = fitsdata_
def main():
    import os
    import argparse
    import multiprocessing
    # Do args & usage
    ap = argparse.ArgumentParser(description="Enrich click data with Simbad fields. "+
                                 "Takes click data as FITS file")
    ap.add_argument("file",type=str,
                    help="Path to FITS file with click data")
    ap.add_argument("--outfile",type=str,required=False,
                    help="Where to write results")
    ap.add_argument("--batchsize",type=int,default=8192)
    ap.add_argument("--maxprocs",type=int,default=8)
    ap.add_argument("--skipto",type=int,default=0)
    ap.add_argument("--runto",type=int,default=None)
    args = ap.parse_args()
    # Validate / finalize args
    fitsdata = fits.open(args.file,memmap=True)[1].data
    if args.runto is None:
        args.runto = len(fitsdata)
    assert(args.skipto < args.runto)
    if args.outfile == "" or args.outfile is None:
        b,e = os.path.splitext(args.file)
        args.outfile = "%s_processed.csv"%(b)
    print "Will write to",args.outfile
    open(args.outfile,'wb').close() # test file and truncate
    # Divide input into batches
    batches = [(i,min(i+args.batchsize,args.runto))
               for i in xrange(args.skipto,args.runto,args.batchsize)]
    # Create locks
    # Controls write access to csv output file
    writelock = multiprocessing.Lock()
    # Throttles connections to Simbad
    simbadlock = multiprocessing.Lock()
    simbadtime = 0
    # Create workers
    p = multiprocessing.Pool(args.maxprocs,initializer=winit,
                             initargs=(writelock, simbadlock,
                                       simbadtime, args, fitsdata))
    p.map(work,batches)
    
if __name__ == "__main__":
    main()
