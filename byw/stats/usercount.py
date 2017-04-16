def main():
    import argparse
    import byw.formats.annotation as annots
    ap = argparse.ArgumentParser(
        description="Count stats abt users from annotations csv")
    ap.add_argument("annotations",
                    help="annotation CSV format file, created with "+
                    "annotationextract")
    args = ap.parse_args()
    ips = set()
    ids = {}

    rdr = annots.AnnotationReader(args.annotations)
    while True:
        a = rdr.readline()
        if not a: break
        if a.user_id != '':
            # non-null user_id
            if a.user_id not in ids:
                ids[a.user_id] = set()
            ids[a.user_id].add(a.user_ip)
        else:
            # null user
            ips.add(a.user_ip)
    print "Total unique users",len(ids)
    total_ips = 0
    for uid in ids:
        total_ips += len(ids[uid])
    print "Average number of unique IPs used by registered user:",total_ips/float(len(ids))
    print "Total unique IPs from non-registered users",len(ips)
    srt_ids = sorted(ids,key=lambda x:len(ids[x]),reverse=True)
    print "Registered users with the most IPs:"
    for id_ in srt_ids[:4]:
        print "  ",id_,len(ids[id_])

if __name__ == "__main__":
    main()
