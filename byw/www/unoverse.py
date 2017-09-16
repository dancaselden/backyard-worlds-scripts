from StringIO import StringIO
from tempfile import NamedTemporaryFile

import csv
import tarfile
import urllib
import subprocess
import json

from flask import Flask
from flask import make_response
from flask import render_template
from flask import send_file
from flask import jsonify
from flask_restful import Api
from flask_restful import Resource
from flask_restful import reqparse
from flask_restful import inputs

import requests

# Image processing
import numpy as np
import astropy.io.fits as aif
import skimage.exposure as skie
import skimage.util.dtype as skid
from PIL import Image,ImageOps
import astropy.visualization as av
import matplotlib.pyplot as plt

import byw.www.xref as xref
import byw.www.image_parsing as imp
import byw.common.radetree as radetree



app = Flask(__name__)
api = Api(app)
app.config['PROPAGATE_EXCEPTIONS'] = True

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

GREY = [
    "gradient:white-black",
]

SUBJECTS, RDTREE = xref.read_cache("wsubcache.csv")
                                                    
# input fits img data, receive png data
def convert_img(file_data,color,mode,linear,trimbright,right_pad=False):
    img = aif.getdata(StringIO(file_data))        
    sim = imp.complex(img,mode,linear,trimbright)
    #sim = skie.rescale_intensity(img,out_range=(0,1))
    opt_img = skid.img_as_ubyte(sim)
    sio = StringIO()
    im = ImageOps.invert(Image.fromarray(opt_img)).transpose(Image.FLIP_TOP_BOTTOM)
    if color is not None:
        plt.imsave(sio,im,format="png",cmap=color)
    else:
        im.save(sio,format="png")
    return sio.getvalue()

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


def get_cutouts(ra, dec, size, band, version, mode, color, linear, trimbright):
    images = {1:[],2:[]}
    for band in images:
        try:
            cutouts = request_cutouts(ra, dec, size, band, version)
        except Exception as e:
            return "Error: {0}".format(str(e)), 500

        converted = []
        for offset, cutout in enumerate(cutouts):
            #pad = offset != len(cutouts)
            #im = convert_img(cutout.read(), None, linear,
            #                 trimbright, right_pad=pad)
            #converted.append(im)
            # Convert from fits
            im = aif.getdata(StringIO(cutout.read()))
            images[band].append(im)

    if len(images[1]) != len(images[2]):
        return "Got imbalanced number of cutouts for W1 and W2", 500

    # Pair W1 and W2 cutouts
    images = [(images[1][i],images[2][i]) for i in xrange(len(images[1]))]

    rgb_images = []
    for w1,w2 in images:
        # Complex scales to 0,1, works w/ uint
        w1 = imp.complex(w1,mode,linear,trimbright)
        w2 = imp.complex(w2,mode,linear,trimbright)
        # Invert
        w1 = 1-w1
        w2 = 1-w2
        # Scale to 0,255
        w1 = skid.img_as_ubyte(w1)
        w2 = skid.img_as_ubyte(w2)
        # merge images
        sio = StringIO()
        arr = np.zeros((w1.shape[0],w1.shape[1],3),"uint8")
        arr[..., 0] = w1
        arr[..., 1] = np.mean([w1,w2],axis=0)
        arr[..., 2] = w2
        #im = ImageOps.invert(Image.fromarray(arr)).transpose(Image.FLIP_TOP_BOTTOM)
        im = Image.fromarray(arr).transpose(Image.FLIP_TOP_BOTTOM)
        im.save(sio,format="png")
        rgb_images.append(sio.getvalue())

    # Merge images
    return StringIO(merge_imgs(rgb_images)), 200


def get_cutout(ra, dec, size, band, version, mode, color, linear, trimbright):
    try:
        cutouts = request_cutouts(ra, dec, size, band, version)
    except Exception as e:
        return "Error: {0}".format(str(e)), 500

    converted = []
    for offset, cutout in enumerate(cutouts):
        pad = offset != (len(cutouts) - 1)
        converted.append(convert_img(cutout.read(), color, mode, linear,
                                     trimbright, right_pad=pad))

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
        parser.add_argument("mode", type=str, default="adapt",
                            choices=["adapt","percent","fixed"])
        parser.add_argument("color", type=str, default="Greys",
                            choices=["viridis","plasma","inferno","magma","Greys","Purples","Blues","Greens","Oranges","Reds","YlOrBr","YlOrRd","OrRd","PuRd","RdPu","BuPu","GnBu","PuBu","YlGnBu","PuBuGn","BuGn","YlGn","binary","gist_yarg","gist_gray","gray","bone","pink","spring","summer","autumn","winter","cool","Wistia","hot","afmhot","gist_heat","copper","PiYG","PRGn","BrBG","PuOr","RdGy","RdBu","RdYlBu","RdYlGn","Spectral","coolwarm","bwr","seismic","Pastel1","Pastel2","Paired","Accent","Dark2","Set1","Set2","Set3","tab10","tab20","tab20b","tab20c","flag","prism","ocean","gist_earth","terrain","gist_stern","gnuplot","gnuplot2","CMRmap","cubehelix","brg","hsv","gist_rainbow","rainbow","jet","nipy_spectral","gist_ncar"])
        parser.add_argument("linear",type=float,default=0.2)
        parser.add_argument("trimbright",type=float,default=99.2)
        args = parser.parse_args()

        if args.linear <= 0.0: args.linear = 0.0000000001
        elif args.linear > 1.0: args.linear = 1.0

        if args.trimbright <= 0.0: args.trimbright = 0.0000000001
        elif args.mode == "percent" and args.trimbright > 100.0: args.trimbright = 100.0

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
            "autoscale": 98.00,
            "output_size": 256
        })
        return url


api.add_resource(Pawnstars_Composite, "/pawnstars")



class Search_Page(Resource):
    def get(self):
        return make_response(render_template("flash.html"))


api.add_resource(Search_Page, "/wiseview")



class Xref_Page(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument("ra", type=float, required=True)
        parser.add_argument("dec", type=float, required=True)
        args = parser.parse_args()

        subs = RDTREE.in_objs(radetree.Point(None,args.ra,args.dec))
        return jsonify({"ids":[str(s.entry.subject_id) for s in subs]})


api.add_resource(Xref_Page, "/xref")



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

    
