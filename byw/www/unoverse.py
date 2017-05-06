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


# input fits img data, receive png data
def convert_img(file_data, equalize=False, lutf="", right_pad=False):
    inf = NamedTemporaryFile(suffix=".fits")
    inf.write(file_data)
    inf.seek(0)

    tmp = None
    if lutf:
        tmp = NamedTemporaryFile(suffix=".png")
        tmp.write(lutf)
        tmp.seek(0)
        lutf = "{0} -clut".format(tmp.name)

    eql = "-equalize" if equalize else ""
    pad = "-background black -gravity East -splice 5x0+0+0" if right_pad else ""
    command = "convert {inf} {eql} {lutf} {pad} png:-".format(inf=inf.name, eql=eql, lutf=lutf, pad=pad)
    return subprocess.check_output(command, shell=True)


def merge_imgs(file_datas, suffix=".png"):
    temp_files = []
    for file_data in file_datas:
        inf = NamedTemporaryFile(suffix=suffix)
        inf.write(file_data)
        inf.seek(0)  
        temp_files.append(inf)

    joined_names = " ".join(map(lambda f: f.name, temp_files))
    command = "convert -background black {imgs} +append png:-".format(imgs=joined_names)
    return subprocess.check_output(command, shell=True)


def create_lut(gradient=GRAD, brighten=0):
    command = "convert -size 5x20 {grad} {black} -append png:-".format(
        grad=" ".join(gradient),
        black='gradient:black-black ' * brighten)
    return subprocess.check_output(command, shell=True)


def find_tar_fits(tar_data):
    targz = tarfile.open(fileobj=StringIO(tar_data), mode="r:gz")
    fits_files = []
    for member in targz.getmembers():
        if member.name.endswith(".fits"):
            cutout = targz.extractfile(member)
            fits_files.append(cutout)  
    return fits_files


def request_cutouts(ra, dec, size, band, version):
    url = PATH.format(ra=ra, dec=dec, size=size, band=band, version=version)
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Invalid response")

    cutouts = find_tar_fits(response.content)
    if not cutouts:
        raise Exception("No fits files found")

    return cutouts


def get_cutouts(ra, dec, size, band, version, brighten, equalize):
    images = []
    for band in (1,2):
        try:
            cutouts = request_cutouts(ra, dec, size, band, version)
        except Exception as e:
            return "Error: {0}".format(str(e)), 500

        converted = []
        for offset, cutout in enumerate(cutouts):
            pad = offset != len(cutouts)
            converted.append(convert_img(cutout.read(), equalize=equalize, right_pad=pad))

        images.append(merge_imgs(converted))

    infs = []
    for image in images:
        inf = NamedTemporaryFile(suffix=".png")
        inf.write(image)
        inf.seek(0)
        infs.append(inf)
    outf = NamedTemporaryFile(suffix=".png")
    cmd = "convert {inf2} {inf1} -background black -channel RB -combine -".format(inf1=infs[0].name,inf2=infs[1].name)
    image = subprocess.check_output(cmd,shell=True)

    return StringIO(image), 200


def get_cutout(ra, dec, size, band, version, brighten, equalize):
    lut = create_lut(brighten=brighten)

    try:
        cutouts = request_cutouts(ra, dec, size, band, version)
    except Exception as e:
        return "Error: {0}".format(str(e)), 500

    converted = []
    for offset, cutout in enumerate(cutouts):
        pad = offset != (len(cutouts) - 1)
        converted.append(convert_img(cutout.read(), equalize=equalize, lutf=lut, right_pad=pad))

    image = merge_imgs(converted)

    return StringIO(image), 200


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
        parser.add_argument("size", type=int, required=True)
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
            "size": args.size,
            "wcs": 1,
            "asinh": True,
            "autoscale": 99.75,
            "output_size": 256
        })
        return url


api.add_resource(Pawnstars_Composite, "/pawnstars")



class Search_Page(Resource):
    def get(self):
        return make_response(render_template("flash.html"))


api.add_resource(Search_Page, "/wiseview")



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

    
