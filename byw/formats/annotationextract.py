"""
Read through the classifications csv and write out each annotation
as a new row
"""
import json
import requests

import byw.formats.zooclassification as ccsv
import byw.formats.classification as clsf
import byw.formats.annotation as annot
import byw.formats.subject as subj
import byw.common.pixelconv as pxc

def zooget(endpoint,kwargs):
    """
    Perform a GET request to zooniverse's API
    """
    heads = {
        "accept":"application/vnd.api+json; version=1",
        "accept-encoding":"gzip, deflate, sdch, br",
        "accept-language":"en-US,en;q=0.8",
        "content-type":"application/json",
    }
    parms = '&'.join(['%s=%s'%(k,kwargs[k]) for k in kwargs])
    return requests.get("https://www.zooniverse.org/api/%s?%s"%(endpoint,parms),
                        headers=heads)

def fetch_workflows():
    """
    Lookup valid workflow_ids for this project
    """
    print "[+] Getting project ...",
    p = zooget("projects",{"id":2416})
    if p.status_code != 200:
        raise Exception("Error %d contacting zooniverse servers"%p.status_code)
    pjs = p.json()
    proj = pjs['projects'][0]
    wflows = proj['links']['workflows']
    if len(wflows) == 0:
        raise Exception("Error: no workflows")
    return wflows

def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Read Zooniverse format classifications and write out "+
        " annotations to a CSV")
    ap.add_argument("classifications",
                    help="Input file of Zooniverse format classifications")
    ap.add_argument("subjects",
                    help="Input file of parsed subject CSV format")
    ap.add_argument("out_annotations",
                    help="Output file for annotations in CSV")
    ap.add_argument("out_classifications",
                    help="Output file for classifications in CSV")
    args = ap.parse_args()
    wflows = fetch_workflows()
    print wflows
    # Read in subjects
    print "Reading subjects"
    subjects = {}
    rdr = subj.SubjectReader(args.subjects)
    while True:
        s = rdr.readline()
        if not s: break
        subjects[int(s.subject_id)] = s
    print "Reading classifications"
    rdr = ccsv.ZooClassificationReader(args.classifications)
    oannot = open(args.out_annotations,'wb')
    oannot.write(annot.AnnotationHeader)
    oannot.write('\n')
    oclassi = open(args.out_classifications,'wb')
    oclassi.write(clsf.ClassificationHeader)
    oclassi.write('\n')
    # Whole file stats tracking
    missing_subject = 0
    invalid_wflow = 0
    missing_dimensions = 0
    bad_annotation = 0
    i = 1
    while True:
        if i %10000 == 0:
            print i
        i += 1
        l = rdr.readline()
        if not l: break
        # Per entry stats tracking
        n_annots = 0
        # Got a ZooClassification.
        # Make sure its for one of our workflows
        if l.workflow_id not in wflows:
            # Sometimes it's not... weird
            invalid_wflow += 1
            continue
        # Get subject metadata
        m = json.loads(l.metadata)
        # Get annotation metadata
        j = json.loads(l.annotations)
        # Extract dimensions
        if not 'subject_dimensions' in m:
            # Hm...
            missing_dimensions += 1
            continue
        for sd in m['subject_dimensions']:
            # Sometimes its 'None'
            if sd is None:
                continue
            natural_width = float(sd['naturalWidth'])
            natural_height = float(sd['naturalHeight'])
            break
        else:
            # No dimensions found :(
            missing_dimensions += 1
            continue
        # Lookup subject
        sid = int(l.subject_ids)
        if not sid in subjects:
            missing_subject += 1
            continue
        s = subjects[sid]
        for task in j:
            # Clicks are all under task T1
            if task['task'] != "T1": continue
            if not 'value' in task or task['value'] is None: # hehe
                print l
                print
                print task
                print '-------'
                continue
            for j in xrange(len(task['value'])):
                # Get click
                click = task['value'][j]
                if click is None or not 'x' in click or not 'y' in click:
                    # Bad annotation
                    bad_annotation += 1
                    continue
                x = float(click['x'])
                y = float(click['y'])
                if x < 0 or x > 532:
                    # Bad X click
                    continue
                if y < 0 or y > 528:
                    # Bad Y click
                    continue
                if click is None:
                    # Sometime's theres a None value there?
                    continue
                # Find ra,de of click
                ra,de = pxc.pixelconv(float(s.ra),float(s.de),
                                      x,y,
                                      int(natural_width)-512,
                                      int(natural_height)-512)
                # Build & write annotation
                a = annot.Annotation(l.classification_id,
                                     str(click['frame']),
                                     str(x),
                                     str(y),
                                     str(ra),
                                     str(de))
                oannot.write(','.join([str(k) for k in a]))
                oannot.write('\n')
                n_annots += 1
        c = clsf.Classification(l.classification_id,
                                l.user_name,
                                l.user_id,
                                l.user_ip,
                                l.subject_ids,
                                n_annots)
        oclassi.write(','.join([str(k) for k in c]))
        oclassi.write('\n')
    print "Missing subjects",missing_subject
    print "Missing dimensions",missing_dimensions
    print "Invalid wflow",invalid_wflow
    print "Bad annotations",bad_annotation
if __name__ == "__main__":
    main()
