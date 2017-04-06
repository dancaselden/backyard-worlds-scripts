def get_subtile(tile,xll,yll):
    return int((tile*64)+((xll/256)*8)+(yll/256))
def get_subtile_from_row(r):
    return get_subtile(int(r[2]),float(r[7]),float(r[8]))

