"""
Extract portions of Subject rows into a smaller and
well formed csv

You may wish to de-duplicate rows afterwards, like:
uniq your_csv > deduped_csv
"""

def main():
    import sys
    import json
    import argparse
    import byw.formats.zoosubject as zsub
    import byw.formats.subject as subj
    ap = argparse.ArgumentParser(
        description="Extract ZooSubject rows into Subject rows "+
        "and write to a new csv")
    ap.add_argument("zoosubjects",
                    help="Input file of Zooniverse Subject format files")
    ap.add_argument("outfile",
                    help="Where to write the output CSV")
    args = ap.parse_args()
    rdr = zsub.ZooSubjectReader(args.zoosubjects)
    of = open(args.outfile,'wb')
    of.write(subj.SubjectHeader)
    of.write('\n')
    while True:
        o = rdr.readline()
        if not o: break
        # Extract RA, DE from metadata
        js = json.loads(o.metadata)
        if 'RA' in js and 'dec' in js:
            # Oldest format
            ra = js['RA']
            de = js['dec']
        elif 'subtile_center' in js:
            # Older format
            splt = js['subtile_center'].split(' ')
            ra,de = splt[1],splt[3]
        elif 'subtile center' in js:
            # Old format
            splt = js['subtile center'].split(' ')
            ra,de = splt[1],splt[3]
        elif ' subtile center' in js:
            splt = js[' subtile center'].split(' ')
            ra,de = splt[1],splt[3]
        else:
            raise Exception("Ill-formed subject row: %s"%str(o))
        s = subj.Subject(o.subject_id,ra,de)
        of.write(','.join(s))
        of.write('\n')

if __name__ == "__main__":
    main()
