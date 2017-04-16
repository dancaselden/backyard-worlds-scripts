"""
Read through the classifications csv and write out each annotation
as a new row
"""
import json
import requests

import zooclassification as ccsv
import annotation as annot

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
    ap.add_argument("outfile",
                    help="Output file for annotations in CSV")
    args = ap.parse_args()
    wflows = fetch_workflows()
    print wflows
    c = ccsv.ZooClassificationReader(args.classifications)
    of = open(args.outfile,'wb')
    of.write(annot.AnnotationHeader)
    of.write('\n')
    i = 1
    while True:
        l = c.readline()
        if not l: break
        # Got a ZooClassification.
        # Make sure its for one of our workflows
        if l.workflow_id not in wflows:
            # Sometimes it's not... weird
            continue
        # Break it out into Annot
        j = json.loads(l.annotations)
        for task in j:
            # Clicks are all under task T1
            if task['task'] != "T1": continue
            if not 'value' in task or task['value'] is None: # hehe
                print l
                print
                print task
                print '-------'
                continue
            for click in task['value']:
                if click is None:
                    # Sometime's theres a None value there?
                    continue
                a = annot.Annotation(l.classification_id,
                                     l.user_id,
                                     l.user_ip,
                                     l.subject_ids,
                                     str(click['frame']),
                                     str(click['x']),
                                     str(click['y']))
                of.write(','.join(a))
                of.write('\n')
        if i %10000 == 0:
            print i
        i += 1
if __name__ == "__main__":
    main()
