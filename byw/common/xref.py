import os
import sys

def get_subtile(tile,xll,yll):
    return int((tile*64)+((xll/256)*8)+(yll/256))

def get_subtile_from_row(r):
    return get_subtile(int(r[2]),float(r[7]),float(r[8]))

def get_subject_file(subtile,fname):
    f = open(fname,'rb')
    f.seek((subtile*25)+12,os.SEEK_SET)
    b = f.read(12)
    return int(b)

def get_subject_buffer(subtile,buf):
    return int(buf[(subtile*25)+12:(subtile*25)+12+12])

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Convert tile, X_UNWISE_LL, Y_UNWISE_LL"+
                                 " to subtile and subject id")
    ap.add_argument("tile",type=int)
    ap.add_argument("x_unwise",type=float)
    ap.add_argument("y_unwise",type=float)
    ap.add_argument("--xreffile",type=str,required=False)
    args = ap.parse_args()
    subt = get_subtile(args.tile,args.x_unwise,args.y_unwise)
    if args.xreffile is not None:
        subj = get_subject_file(subt,args.xreffile)
        print ("https://www.zooniverse.org/projects/marckuchner/"+
               "backyard-worlds-planet-9/talk/subjects/%d"%subj)
    else:
        print "Subtile:",subt

if __name__ == "__main__":
    main()
