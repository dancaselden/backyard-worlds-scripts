import json
import requests

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
    import byw.formats.zooclassification as zooc
    ap = argparse.ArgumentParser(
        description="Count stats abt users from zooniverse clasification csv")
    ap.add_argument("classifications")
    args = ap.parse_args()
    ips = set()
    ids = {}
    names = set()
    registered_total_ips = set()
    wflows = fetch_workflows()
    invalid_wflows = 0
    
    rdr = zooc.ZooClassificationReader(args.classifications)
    while True:
        a = rdr.readline()
        if not a: break
        if a.workflow_id not in wflows:
            invalid_wflows += 1
            continue
        if a.user_id != '':
            # non-null user_id
            if a.user_id not in ids:
                ids[a.user_id] = set()
            ids[a.user_id].add(a.user_ip)
            registered_total_ips.add(a.user_ip)
        else:
            # null user
            ips.add(a.user_ip)
        if not a.user_name.startswith('not-logged-in'):
            # classification had a logged-in username
            names.add(a.user_name)
            if len(a.user_id) == 0:
                print "WOAHHHHH NELLY"
                print a
    print "Total unique users ids",len(ids)
    print "Total unique user names",len(names)
    print "Global total registered user ips",len(registered_total_ips)
    total_ips = 0
    for uid in ids:
        total_ips += len(ids[uid])
    print "Average number of unique IPs used by registered user:",total_ips/float(len(ids))
    print "Total unique IPs from non-registered users",len(ips)
    srt_ids = sorted(ids,key=lambda x:len(ids[x]),reverse=True)
    print "Registered users with the most IPs:"
    for id_ in srt_ids[:4]:
        print "  ",id_,len(ids[id_])
    print "num classifications with other project's wflow id",invalid_wflows

if __name__ == "__main__":
    main()
