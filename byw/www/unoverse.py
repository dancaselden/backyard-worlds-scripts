from StringIO import StringIO
from tempfile import NamedTemporaryFile

import csv
import tarfile
import urllib
import subprocess

from flask import Flask
from flask import make_response
from flask import render_template
from flask import send_file
from flask_restful import Api
from flask_restful import Resource
from flask_restful import reqparse
from flask_restful import inputs

import requests



app = Flask(__name__)
api = Api(app)


PATH = "http://unwise.me/cutout_fits?file_img_m=on&version={version}&ra={ra}&dec={dec}&size={size}&bands={band}"


GRAD = [
    "gradient:blueviolet-blue",
    "gradient:blue-cyan",
    "gradient:cyan-green1",
    "gradient:green1-yellow",
    "gradient:yellow-orange",
    "gradient:orange-red",
    "gradient:red-black",
]

def get_cutouts(ra, dec, size, band, version, brighten, equalize):
    images = []
    for band in (1,2):
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
                cutouts.append(cutout)

        if not cutouts:
            return ("Failed to extract fits file from response", 500)

        # Equalize or no?
        eql = "-equalize" if equalize else ""
        outfs = []
        for offset, cutout in enumerate(cutouts):
            if (offset + 1) == len(cutouts):
                command = "convert {inf} {eql} -scale 500% {outf}"
            else:
                command = "convert {inf} {eql} -scale 500% -background black -gravity East -splice 5x0+0+0 {outf}"

            # Write fits file to disk
            inf = NamedTemporaryFile(suffix=".fits")
            inf.write(cutout.read())
            inf.seek(0)

            outf = NamedTemporaryFile(suffix=".png")
            outfs.append(outf)

            # Convert img with imagemagick
            subprocess.check_output(command.format(inf=inf.name, outf=outf.name, eql=eql), shell=True)

        # Stitch images together
        images.append(subprocess.check_output("convert -background black {0} +append -".format(" ".join([outf.name for outf in outfs])), shell=True))

    infs = []
    for image in images:
        inf = NamedTemporaryFile(suffix=".png")
        inf.write(image)
        inf.seek(0)
        infs.append(inf)
    outf = NamedTemporaryFile(suffix=".png")
    cmd = "convert {inf2} {inf1} -background black -channel RB -combine -".format(inf1=infs[0].name,inf2=infs[1].name)
    image = subprocess.check_output(cmd,shell=True)

    return StringIO(image), response.status_code


def get_cutout(ra, dec, size, band, version, brighten, equalize):
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
            cutouts.append(cutout)

    if not cutouts:
        return ("Failed to extract fits file from response", 500)

    # Build LUT
    lutf = NamedTemporaryFile(suffix=".png")
    command = ("convert -size 5x20 {grad} {black} -append {lutf}").format(
        grad=" ".join(GRAD),
        black='gradient:black-black ' * brighten, 
        lutf=lutf.name)
    subprocess.check_output(command, shell=True)

    # Equalize or no?
    eql = "-equalize" if equalize else ""
    outfs = []
    for offset, cutout in enumerate(cutouts):
        if (offset + 1) == len(cutouts):
            command = "convert {inf} {eql} {lutf} -clut {outf}"
        else:
            command = "convert {inf} {eql} {lutf} -clut -background black -gravity East -splice 5x0+0+0 {outf}"

        # Write fits file to disk
        inf = NamedTemporaryFile(suffix=".fits")
        inf.write(cutout.read())
        inf.seek(0)

        outf = NamedTemporaryFile(suffix=".png")
        outfs.append(outf)

        # Convert img with imagemagick
        subprocess.check_output(command.format(inf=inf.name, outf=outf.name, lutf=lutf.name, eql=eql), shell=True)

    # Stitch images together
    image = subprocess.check_output("convert -background black {0} +append -".format(" ".join([outf.name for outf in outfs])), shell=True)

    return StringIO(image), response.status_code


class Convert(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument("ra", type=float, required=True)
        parser.add_argument("dec", type=float, required=True)
        parser.add_argument("size", type=int, default=100)
        parser.add_argument("band", type=int, default=3, choices=[1,2,3])
        parser.add_argument("version", type=str, default="neo2", 
                                    choices=["allwise", "neo1", "neo2"])
        parser.add_argument("brighten", type=int, default=0,
                            choices=range(1028)) # TODO: dammit dan
        parser.add_argument("equalize", type=inputs.boolean,
                            default=True)
        args = parser.parse_args()

        if args.band in (1,2):
            cutout, status = get_cutout(**args)
        else:
            cutout, status = get_cutouts(**args)
            if status != 200:
                return "Request failed", 500

        return send_file(cutout, mimetype="image/png")   


api.add_resource(Convert, "/convert")


class Pawnstars_Composite(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument("ra", type=float, required=True)
        parser.add_argument("dec", type=float, required=True)
        args = parser.parse_args()

        response = requests.get("http://ps1images.stsci.edu/cgi-bin/ps1filenames.py", params={
            "RA": args.ra,
            "DEC": args.dec,
            "filters": "giy",
            "sep": "comma"
        })

        files = {}
        reader = csv.DictReader(StringIO(response.content))
        for row in reader:
            files[row["filter"]] = row["filename"]

        url = "http://ps1images.stsci.edu/cgi-bin/fitscut.cgi?" + urllib.urlencode({
            "red": files["y"],
            "green": files["i"],
            "blue": files["g"],
            "x": args.ra,
            "y": args.dec,
            "size": 60,
            "wcs": 1,
            "asinh": True,
            "autoscale": 99.75,
            "output_size": 512
        })
        return url


api.add_resource(Pawnstars_Composite, "/pawnstars")



class Search_Page(Resource):
    def get(self):
        return make_response(render_template("flash.html"))


api.add_resource(Search_Page, "/wiseview")



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

    
