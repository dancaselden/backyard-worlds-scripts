"""
Get byw subjects, and provide a coordinate-based lookup.
This all needs to be re-written to support WCS.
"""
import os.path
import requests
import argparse
import time
import numpy as np


import byw.common.rdballtree as rdbt
import astropy.table as at # need to do this first, or astropy will barf?
import astropy.io as aio

import byw.formats.workflowsubject as wsub
import byw.formats.subjectextract as sube


BYW_PROJ_ID = 2416

# Field of View of a flipbook in degrees
byw_fov = np.sqrt(((0.0975*2)**2)*2)

# Hold all the subjects by center coordinate in a balltree
subject_tree = None


def get_subjects_by_coordinates(ra,dec):
    # Get subjects within fov
    res = subject_tree.query_radius(ra,dec,byw_fov)

    # Sort by nearest
    res = [(res[0][0][i],res[1][0][i]) for i in xrange(len(res[0][0]))]
    
    return sorted(res,key=lambda x: x[1])
    

def get(endpoint,kwargs):
    """HTTP GET with accepted headers"""
    heads = {
        "accept":"application/vnd.api+json; version=1",
        "accept-encoding":"gzip, deflate, sdch, br",
        "accept-language":"en-US,en;q=0.8",
        "content-type":"application/json",
    }
    parms = '&'.join(['%s=%s'%(k,kwargs[k]) for k in kwargs])
    return requests.get("https://www.zooniverse.org/api/%s?%s"%
                        (endpoint,parms),headers=heads)


def get_subjects_page(wflow, page, pagesz):
    res = []
    subs = get("subjects",{"sort":"cellect",
                            "workflow_id":wflow,
                            "page":page,
                            "page_size":pagesz})
    if subs.status_code != 200:
        print "Error getting subjects",subs.status_code
        print subs.text
        return subs.status_code,res

    # Extract subject ids and subtile center coordinates
    # from metadata
    js = subs.json()
    try:
        for sub in js['subjects']:
            id_ = int(sub['id'],10)
            meta = sub['metadata']
            ra, de = sube.radec_from_metadata(meta)
            ra = float(ra)
            de = float(de)
            res.append(wsub.WorkflowSubject(wflow, id_, ra, de))
    except KeyError, e:
        # TODO: handle some errors
        raise
    
    return subs.status_code, res


def get_subjects(subs):
    """
    get_subjects searches for workflows for the byw/p9
    project on zooniverse, then searches for all subjects
    under each workflow

    subs is a dictionary of already captured subjects

    get_subjects returns the updated subs
    """
    # Get project metadata by ID
    p = get("projects",{"id":2416})
    if p.status_code != 200:
        print "error",p.status_code
        sys.exit(-1)

    # Get workflows from project metadata
    pjs = p.json()
    proj = pjs['projects'][0]
    wflows = proj['links']['workflows']
    if len(wflows) == 0:
        print "Error: No workflows"
        sys.exit(-1)

    # Convert to ints
    wflows = [int(w,10) for w in wflows]

    # Build dict to hold new subjects
    new_subs = {}
    for w in wflows:
        new_subs[w] = []

    PAGESZ = 200
    # For each workflow, update subjects until there are no more
    for w in wflows:
        while True:
            # Calculate which page to download based upon
            # how many subs of this workflow we have
            numsubs = 0 if w not in subs else len(subs[w])
            numsubs += len(new_subs[w])
            pg = numsubs/PAGESZ
            ok = False
            # Retry 5 times
            for i in xrange(5):
                code, subs_ = get_subjects_page(w, pg, PAGESZ)
                if code != 200:
                    print "Error getting wflow",w,pg,PAGESZ,code
                    continue
                ok = True
                break
            
            # Something is going wrong...
            if not ok:
                # Move on to next workflow
                break

            # If numsubs % PAGESZ != 0, then we already have
            # some of the subs from previous queries.
            # To avoid duplicates, only add subs from this
            # page beyond previous numsubs
            subs_ = subs_[numsubs % PAGESZ:]
            new_subs[w].extend(subs_)
            
            if len(subs_) != PAGESZ:
                # No more subjects to fetch.
                # move on to next workflow
                print "No more to fetch",w,numsubs
                break
        
    return new_subs


def read_cache(cachepath):
    # Put a header on the cache if it doesn't
    # yet exist
    if not os.path.exists(cachepath):
        open(cachepath,'wb').write(wsub.WorkflowSubjectHeader+'\n')

    # Load subjects
    tbl = aio.ascii.Csv().read(cachepath)

    # Store in balltree (it's faster w/o a cache)
    rdtree = rdbt.rdtree(tbl,#filename="%s.rdbtcache"%cachepath,
                         rakey="ra",deckey="de")

    return rdtree


def poll_subjects(subs,rdtree,cachepath):
    # Poll get_subjects
    # Update cache if any
    while True:
        new_subs = get_subjects(subs)

        # Update cache
        f = open(cachepath,'ab')
        for w in new_subs:
            for s in new_subs[w]:
                f.write(','.join([str(v) for v in s]))
                f.write('\n')
        f.close()

        # Add to greater subs data struct
        for w in new_subs:
            if w in subs:
                subs[w].extend(new_subs[w])
            else:
                subs[w] = new_subs[w]

        # TODO: locking
        # TODO: only store num of subs in subs{},
        #       that way its not in memory twice
        #       (one in radetree, one in subs)
        # Update radetree
        for w in new_subs:
            for s in new_subs[w]:
                rdtree.add(radetree.BBox_new_subject(s))

        # Sleep for next iteration
        # Give poor zooniverse a break
        print "Sleeping"
        time.sleep(60*5)


def __init(cachepath):
    """Populate subject_tree"""
    global subject_tree

    subject_tree = read_cache(cachepath)


def main():
    __init("wsubcache.csv")

    raise Exception("Well, it'll be half a year from today, and dan will be mad with himself. It's time to update poll_subjects to support the rdbt structure. this time, don't forget to use an existing wsubcache to start polling. it'll be faster")
    poll_subjects("wsubcache.csv")

    
if __name__ == "__main__": main()
else: __init("wsubcache.csv")
