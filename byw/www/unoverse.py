from StringIO import StringIO
from tempfile import NamedTemporaryFile
import re
import tarfile
import os
import subprocess

from astropy.io import fits
from flask import Flask
from flask import make_response
from flask import render_template
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
    targz = tarfile.open(fileobj=StringIO(response.content), mode="r:gz")
    cutouts = []
    for member in targz.getmembers():
        print member.name
        if member.name.endswith(".fits"):
            cutout = targz.extractfile(member)
            data = cutout.read()
            cutout.seek(0)
            cutouts.append(cutout)

    if len(cutouts) == 0:
        return ("Failed to extract fits file from response", 500)

    outfs = []
    for cutout in cutouts:
        # Write fits file to disk
        inf = NamedTemporaryFile(suffix=".fits")
        inf.write(cutout.read())
        inf.seek(0)

        outf = NamedTemporaryFile(suffix=".png")
        outfs.append(outf)

        # Convert img with imagemagick
        command = "convert {inf} lut.png -clut -scale 500% {outf}".format(inf=inf.name, outf=outf.name)
        subprocess.check_output(command, shell=True)

        # Cleanup
        inf.close()

    # Cleanup
    del cutouts # cleanup
    del targz
        
    # Stitch images together
    final = NamedTemporaryFile(suffix=".png")
    os.system("convert -background black %s +append %s"%(" ".join([outf.name for outf in outfs]), final.name))

    # Read file back to memory
    pic = final.read()

    # Cleanup
    for outf in outfs:
        outf.close()
    final.close()
    
    return pic,response.status_code

class Convert(Resource):
    def get(self):
            parser = reqparse.RequestParser()
            parser.add_argument("ra", type=float, required=True)
            parser.add_argument("dec", type=float, required=True)
            parser.add_argument("size", type=int, required=False,
                                default=100)
            parser.add_argument("band", type=int, required=False,
                                default=2, choices=[1,2])
            parser.add_argument("version", type=str, required=False,
                                default="neo2", choices=["allwise",
                                                         "neo1", "neo2"])
            args = parser.parse_args()

            cutouts = []
            cutout, status = get_cutout(args.ra, args.dec,
                                        args.size, args.band, args.version)
            if status != 200:
                return "Request failed", 500

            return send_file(StringIO(cutout), mimetype="image/png")   


api.add_resource(Convert, "/convert")


class Search_Page(Resource):
    def get(self):
            return make_response(render_template("flash.html"))


api.add_resource(Search_Page, "/search")



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
    #r,sc = get_cutout(230.3699,24.9286,100,"1","neo2")
    #print repr(r[:100])
    
