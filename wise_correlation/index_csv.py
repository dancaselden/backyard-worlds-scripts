import os
import array
import argparse

def index_csv(fname):
    # Use array module to save memory
    # If file is > 4G
    if os.path.getsize(fname) > 0xffffffff:
        a = array.array('Q')
    else:
        a = array.array('L')
    f = open(fname,'rb')
    last = 0
    while True:
        l = f.readline()
        if not l: break
        a.append(last)
        last = f.tell()
    return a
def load_indices(fname):
    f = open(fname,'rb')
    if os.path.getsize(fname) > 0xffffffff:
        a = array.array('Q')
    else:
        a = array.array('L')
    for l in f.readlines():
        a.append(int(l))
    return a
def main():
    ap = argparse.ArgumentParser(description="Index all newlines in csv")
    ap.add_argument("infile")
    ap.add_argument("outfile")
    args = ap.parse_args()
    of = open(args.outfile,'wb')
    for i in index_csv(args.infile):
        of.write(str(i))
        of.write('\n')

if __name__ == "__main__": main()
