from StringIO import StringIO
from tempfile import NamedTemporaryFile
import re
import tarfile
import os

from astropy.io import fits
from flask import Flask
from flask import request
from flask import send_file
from flask_restful import Api
from flask_restful import Resource
from flask_restful import reqparse

import png
import requests
import numpy


app = Flask(__name__)
api = Api(app)


PATH = "http://unwise.me/cutout_fits?file_img_m=on&version={version}&ra={ra}&dec={dec}&size={size}&bands={band}"


def validate_tile(tile):
    try:
        return TILE_RE.search(tile).group(1)
    except AttributeError:
        raise ValueError("Invalid tile name")

def get_cutout(ra, dec, size, band, version):
    # Construct URL to cutout and download
    url = PATH.format(ra=ra, dec=dec, size=size, band=band, version=version)
    print url
    response = requests.get(url)
    if response.status_code != 200:
        return ("Request failed", 500)

    # Extract fits from tar.gz
    targz = tarfile.open(fileobj=StringIO(response.content),mode='r:gz')
    fits_file = None
    for member in targz.getmembers():
        if member.name.endswith('.fits'):
            fits_file = targz.extractfile(member)
            break
    if fits_file is None:
        return ("Failed to extract fits file from response", 500)

    # Write fits file to disk
    inf = NamedTemporaryFile(suffix=".fits")
    inf.write(fits_file.read())
    del fits_file # cleanup
    del targz
    outf = NamedTemporaryFile(suffix=".png")

    # Convert img with imagemagick
    os.system("convert {inf} lut.png -clut -scale 500% {outf}".format(inf=inf.name,outf=outf.name))

    # Read file back to memory
    pic = outf.read()
    inf.close()
    outf.close()
    
    return pic,response.status_code

class Convert(Resource):
    def get(self):
            parser = reqparse.RequestParser()
            parser.add_argument('ra', type=float, required=True)
            parser.add_argument('dec', type=float, required=True)
            parser.add_argument('size', type=int, required=False,
                                default=100)
            parser.add_argument('band', type=int, required=False,
                                default=2, choices=[1,2])
            parser.add_argument('version', type=str, required=False,
                                default="neo2", choices=["allwise",
                                                         "neo1", "neo2"])
            args = parser.parse_args()

            cutouts = []
            cutout, status = get_cutout(args.ra, args.dec,
                                        args.size, args.band, args.version)
            if status != 200:
                return "Request failed", 500

            return send_file(StringIO(cutout), mimetype='image/png')   


api.add_resource(Convert, '/convert')


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
    #r,sc = get_cutout(42,43,100,"1","neo2")
    #print repr(r[:100])
    
