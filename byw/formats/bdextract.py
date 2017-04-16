"""
Extract BDs from Simbad's default sim-coo ascii table format
using simbadascii and store in a well-formed csv
"""

def main():
    import argparse
    import byw.formats.simbadascii as sba
    ap = argparse.ArgumentParser(
        description="Extract BDs from simbadascii format and store in CSV")
    ap.add_argument("simbadascii_table",
                    help="simbadascii table from simbad sim-coo")
    ap.add_argument("output",
                    help="where to write output csv")
    args = ap.parse_args()
    rdr = sba.SimbadAsciiReader(args.simbadascii_table)
    of = open(args.output,'wb')
    of.write(sba.SimbadEntryHeader)
    of.write('\n')
    while True:
        o = rdr.readline()
        if not o: break
        of.write(','.join([str(k) for k in o]))
        of.write('\n')

if __name__ == "__main__":
    main()
    

