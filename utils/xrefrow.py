import sys
import xref
row = sys.stdin.readline().split(',')
subt = xref.get_subtile_from_row(row)
subj = xref.get_subject_file(subt,sys.argv[1])
print ("https://www.zooniverse.org/projects/marckuchner/"+
       "backyard-worlds-planet-9/talk/subjects/%d"%subj)
